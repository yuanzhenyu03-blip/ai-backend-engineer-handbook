# Day99 — Vector Database and Vector Index Design

## 1. Lesson Metadata

```text
Status: Completed (classroom implementation); production evidence incomplete
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 6–8 hours
Prerequisite: Day95–Day98 immutable DocumentVersion, ChunkSet, ACL/provenance and EmbeddingSet
Previous Lesson: Day98 — Embedding Model Selection and Versioning
Next Lesson: Day100 — Hybrid Retrieval and Filtering
Engineering Artifact: authorized immutable shadow VectorIndexGeneration workflow
Production Readiness: MORE_EVIDENCE_NEEDED
```

The repository contains executed local evidence, deterministic fakes and official static research. It does not
claim a real vector database, real ANN performance, distributed recovery or production traffic.

## 2. Learning Objectives

After this lesson, the student can:

- distinguish a vector database from a vector index;
- explain cosine similarity, cosine distance, dot product and L2 direction in plain language;
- distinguish Exact/Flat search from ANN and identify HNSW/IVF build versus query parameters;
- freeze a versioned `VectorIndexContract` without changing Day98 vector semantics;
- authorize one exact `EmbeddingSet` for indexing with a narrow action;
- create deterministic tenant-scoped write batches and correlate every Provider response;
- reject missing, duplicate, unknown and partially acknowledged writes;
- reconcile timeout-unknown outcomes without blind replay;
- build a shadow generation and let only the Committer establish durable application truth;
- explain why a sealed generation may still be ineligible for activation;
- compare pgvector, Qdrant and Pinecone using hard gates before weighted preferences;
- defend the design in an English backend-system interview.

## 3. Why This Matters

Day98 produced vectors, but a tuple of floats is not yet a safe retrieval system. If an application silently
changes the metric, mixes model revisions, overwrites a live namespace, trusts a partial ACK or exposes another
tenant's points, the results can look plausible while being technically wrong.

The production problem is therefore not merely “where do we put arrays?” It is:

```text
How do we preserve vector meaning, identity, authorization and recovery
while making the physical search implementation replaceable?
```

The controls in this lesson reduce five risks:

- correctness: the database cannot redefine score direction or vector compatibility;
- security: namespace equality and metadata filters never replace current authorization;
- reliability: unknown and partial writes cannot become the current generation;
- operability: physical index changes use copy-on-write shadow generations;
- auditability: official facts, simulations, executed evidence and missing evidence stay separate.

## 4. Roadmap Position

```text
Day95 current immutable DocumentVersion
                |
Day96 current selected ChunkSet + source spans
                |
Day97 current tenant authorization + provenance
                |
Day98 current homogeneous EmbeddingSet
                |
                v
Day99 authorized shadow vector generation
  contract -> batches -> Adapter -> readback -> Validator -> Committer
                |
                v
Day100 hybrid retrieval + current authorization + filtering
                |
                v
Day103 retrieval/answer quality evaluation
                |
                v
Day104 update/delete/rebuild/migration
```

The long knowledge chain begins earlier: upload became a durable job and Outbox in Day49–50; authentication,
tenant authorization, Adapter boundaries, timeouts, workers, retries and failure injection were developed in
Day51–58; later Provider, browser, queue, n8n, LLM and Agent/MCP lessons repeatedly separated a proposal from
durable truth. Day99 reuses those same mental models for vector storage.

Day99 does not implement production retrieval. It prepares an input that Day100 may consume only after the
generation is committed, current, homogeneous and fully eligible.

## 5. Lesson Map

```text
official candidate evidence
  -> hard gates
  -> provisional database choice
  -> narrow index-build authorization
  -> freeze VectorIndexContract
  -> deterministic batch plan
  -> Provider Adapter
  -> ACK correlation + authoritative readback
  -> Exact/Flat correctness probes
  -> current-state and fence recheck
  -> immutable shadow generation
  -> optional atomic selected-pointer cutover
  -> Outbox hint
```

Memory picture: Day98 is a batch of coordinates made by one exact machine specification. Day99 is the warehouse
team choosing the shelf design, placing every item on a new shadow shelf, counting it, checking it, and only
then deciding whether the entrance sign may point at it.

## 6. Core Mental Model

```text
EmbeddingSet = immutable coordinate products
VectorIndexContract = shelf + distance + placement specification
VectorIndexCandidate = untrusted proposed shelf
Validator = inventory and quality inspector
VectorIndexGeneration = immutable accepted shelf fact
Selected pointer = mutable entrance sign
Outbox = notification slip, never the shelf or entrance sign
```

The executable lifecycle is:

```text
Day98 Outbox wake-up hint
        |
        v
authoritative reread of current EmbeddingSet
        |
        v
current index-build authorization and lineage check
        |
        v
deterministic batches -> Adapter -> shadow physical generation
        |
        v
exact ACK correlation -> readback -> manifest -> controlled probes
        |
        v
authorization / lineage / set / contract / fence recheck
        |
        v
sole Committer seals immutable generation + Outbox
        |
        +-- incomplete production gates -> remain SEALED, no pointer movement
        |
        `-- all gates PASS -> CAS selected pointer + Outbox atomically
```

## 7. Main Concepts

### Concept 1: Vector database, vector index and the contract

**Tech Lead Question:** Is a vector database the same thing as a vector index?

**Student Thinking:** Both help find nearby vectors, so they can sound interchangeable. The student ultimately
rejected treating them as the same object.

**Student Answer:** No. A database owns persistence and operational APIs; an index is a physical search
structure inside or beside that storage system.

**Tech Lead Review:** A vector database is the warehouse system: storage, point identity, payload, mutation,
durability, backup and query APIs. A vector index is a navigation structure such as Flat, HNSW or IVF. One
database may offer several index types. Faiss can provide indexes without being the durable application
database.

`VectorIndexContract` binds the source EmbeddingContract, model revision, dimensions, float type,
normalization, metric, score orientation, algorithm, build parameters, quantization, Provider/API version,
tenant namespace strategy, point and payload schemas, batch limits, durability expectations and update policy.

```text
same dimensions != same vector space
same model + different preprocessing != same vector space
same vectors + different metric != same index semantics
```

**Engineering Thinking:** Physical compatibility is a versioned contract, not an intuition based on array
length. Changing HNSW `m`, `ef_construction`, IVF `lists`, metric, quantization or physical schema creates a new
generation. Changing `top_k`, threshold, HNSW `ef_search` or IVF `probes` creates a new retrieval-policy
revision, not necessarily a physical rebuild.

**Production Example:** An old cosine threshold cannot be copied to a dot-product contract merely because both
rankings looked similar in a small sample.

**Framework Connection:** The application core uses its own dataclasses. pgvector operators, Qdrant client
models and Pinecone SDK response objects stay behind the Adapter.

### Concept 2: Metric direction, thresholds and Adapter semantics

**Tech Lead Question:** The Provider returns cosine distance `0.18`; the application threshold is similarity
`>= 0.80`. What must the Adapter return?

**Student Thinking:** The raw number cannot be compared directly because smaller distance is better while
larger similarity is better.

**Student Answer:** Return application similarity `0.82`; it passes the threshold.

**Tech Lead Review:** For cosine distance defined as `1 - cosine_similarity`:

```text
application_similarity = 1 - provider_cosine_distance
0.82 = 1 - 0.18
```

For unit-L2 normalized vectors:

```text
cosine_similarity = dot_product
squared_L2 = 2 - 2 * dot_product
```

The ordering may be equivalent, but the numeric value, direction, threshold and database operator remain
different contracts. pgvector's negative-inner-product operator is a database-private representation; the
Adapter must not leak it as an application score.

The threshold operator is explicit. A score of exactly `0.8000` passes `>= 0.8000` and fails `> 0.8000`.
The implementation does not add a hidden epsilon. Epsilon means a tiny tolerance used for floating-point
comparison; silently adding one would change product policy. A tolerance is valid for controlled numeric
round-trip validation only when it is declared and versioned.

**Engineering Thinking:** Display rounding never makes authorization or threshold decisions. Non-finite,
out-of-range, duplicate or wrong-generation Provider hits fail closed.

**Production Example:** A database distance of `0.82` is not an application similarity of `0.82`. Exposing it
without translation can reverse every threshold decision.

### Concept 3: Exact/Flat, HNSW and IVFFlat

**Tech Lead Question:** Why implement Exact/Flat before tuning HNSW or IVF?

**Student Thinking:** ANN is useful for scale, but its error cannot be measured without a trusted answer.

**Student Answer:** Implement Exact/Flat first as the correctness reference.

**Tech Lead Review:** Exact search compares the query with every eligible vector. It is slow at large scale but
provides the gold nearest neighbors. ANN searches fewer candidates and trades recall for latency, memory and
throughput.

```text
Flat     = compare the whole warehouse
HNSW     = follow shortcuts through a multi-layer neighbor graph
IVF      = choose nearby regions/centroids, then search selected regions
```

Graph topology means the pattern of nodes and links in the HNSW graph: which vector is connected to which,
and through which layers. HNSW `m` and `ef_construction` shape that topology at build time. `ef_search` changes
the query exploration budget. IVF `lists`/`nlist` determines how many centroid regions are built; `probes` or
`nprobe` determines how many are searched per query.

`recall@k` asks: “Of the exact top-k identities, what fraction did ANN return?” Rank overlap compares identity
sets in two rankings; it does not by itself measure ordering quality. The executed controlled corpus contains
256 deterministic vectors, two tenant partitions, eight probes and `k=5`. Its fake proposal has mean
recall@5 `0.9`; that verifies the calculation only. Real HNSW/IVF remains `NOT_RUN`.

**Engineering Thinking:** Float32 exact versus half-precision exact isolates quantization error. Half-precision
exact versus half-precision HNSW isolates ANN error. The user-visible comparison is Float32 exact versus the
final half-precision HNSW result.

**Production Example:** Increasing `probes` or `ef_search` can improve recall, but consumes more latency and
work; maximizing the value is not automatically the best policy.

### Concept 4: Narrow authorization and current lineage

**Tech Lead Question:** Does Day98's `chunk:read_for_embedding` permit authorize Day99 indexing?

**Student Thinking:** Both operations touch the same source lineage, but their purposes differ.

**Student Answer:** No; it has not authorized indexing.

**Tech Lead Review:** Day99 uses `embedding_set:read_for_indexing` for service principal `index-builder-a`.
The signed handoff binds the tenant, exact action/audience/purpose, expiry, authorization revisions, document,
version, ChunkSet, exact Chunk and EmbeddingRecord IDs, EmbeddingSet checksum, EmbeddingContract, selected-set
revision and selected VectorIndexContract revision.

The guard checks the same facts before Provider dispatch and immediately before commit. Authorization change,
expiry, inactive membership, provenance drift, selected EmbeddingSet drift, selected contract drift or a stale
fence means zero durable generation transition.

**Engineering Thinking:** Database credentials answer “may this process connect?” They do not answer “may this
principal use this tenant's protected EmbeddingSet for this purpose?” Namespace equality and metadata filters
also do not answer that question.

**Production Example:** ACL-only change does not require recomputing embeddings or rebuilding the physical
index, but it invalidates stale authorization and restricts future reads. A body or chunking change requires a
new EmbeddingSet and therefore a new vector generation.

### Concept 5: Deterministic batches and response correlation

**Tech Lead Question:** Can a successful batch ACK make the generation current?

**Student Thinking:** An ACK proves at most what the Provider says it accepted. Missing points, wrong IDs or a
later consistency delay may still exist.

**Student Answer:** No; it must be correlated and read back.

**Tech Lead Review:** The planner sorts by stable point identity, never changes coordinates, never merges by
content hash, never crosses tenants, obeys item/byte limits and derives stable batch IDs plus a plan checksum.
One vector is never split into multiple vectors.

Each ACK is checked against exact:

```text
request ID + batch ID + tenant + namespace + generation + ordered point IDs
```

Out-of-order ACKs are acceptable because identity correlation is exact. Duplicate, missing, unknown, stale,
wrong-tenant, wrong-namespace, wrong-generation and partial ACKs are rejected. Even complete ACKs remain
candidates until readback proves exact count, exact IDs, vector digest, payload digest and generation binding.

A Provider checkpoint is an opaque marker returned by the storage boundary that identifies the Provider state
observed after a write. It helps tie readback evidence to a particular Provider state; it is not an application
commit, a backup, or proof of durability by itself.

**Engineering Thinking:** The payload carries authoritative application identities—tenant, document version,
ChunkSet, EmbeddingSet, EmbeddingRecord, Chunk and content hash—so the Provider point can be traced without
putting raw protected vectors in ordinary evidence.

### Concept 6: UNKNOWN, reconciliation and fencing

**Tech Lead Question:** A timeout occurs after the write was dispatched. May a new attempt immediately replay
the batch?

**Student Thinking:** Timeout does not reveal whether the Provider executed the request.

**Student Answer:** No. Run reconciliation.

**Tech Lead Review:** `UNKNOWN` is neither success nor proven failure. The original logical `operation_id`
remains stable. A new attempt receives a fresh request identity and Committer-issued fencing token only after
the previous outcome is proven not executed. If authoritative readback proves the original result complete,
the original operation converges to that result instead of processing it twice.

```text
timeout after dispatch
  -> mark UNKNOWN
  -> block blind retry
  -> authoritative readback/status
       |-- complete and matching -> validate and seal same result
       |-- proven not executed   -> allow fresh attempt
       `-- ambiguous             -> remain UNKNOWN
```

An expired lease is not enough to prove the old worker cannot finish. Fencing makes stale commits rejectable.
The old physical bytes may be reusable, but the old worker cannot keep commit authority.

### Concept 7: Shadow generation, selected pointer and Outbox

**Tech Lead Question:** Should a rebuild modify the live generation in place?

**Student Thinking:** In-place mutation mixes old and new states and makes rollback/read consistency unclear.

**Student Answer:** No; use copy-on-write, validate a shadow generation, then switch.

**Tech Lead Review:** The new physical generation is built while the old one remains intact. The Committer is
the sole component allowed to seal an immutable generation. Activation is a separate CAS over the selected
pointer and requires all hard gates, compatible retrieval policy and a fresh activation fence.

```text
G1 current -> build G2 shadow -> validate G2 -> CAS pointer G1 to G2
```

The generation is immutable history; the selected pointer is mutable current truth. A delayed G1 event cannot
roll the pointer backward. Generation commit, pointer CAS and Outbox intent use the application database as
authority. Provider aliases are derived projections.

An Outbox watermark is the highest durable Outbox position known to have been processed. A deletion-ledger
watermark is the analogous progress marker for durable deletion intents. They are recovery cursors, not proof
that a particular Provider side effect happened. Backups must capture mutually compatible application state,
Outbox and deletion-ledger progress; independently timed copies can resurrect deleted or stale generations.

**Production Example:** At-least-once relay may publish the same event twice. Consumers reread the selected
bundle and converge. Missing Outbox delivery cannot fabricate a selection, and a delayed old event is `STALE`.

### Concept 8: Candidate research and evidence levels

**Tech Lead Question:** Can the most popular managed product win before security and recovery facts are known?

**Student Thinking:** Weighted preferences are useful only after non-negotiable gates pass.

**Student Answer:** No; reject the switch or mark it as needing more evidence.

**Tech Lead Review:** Day99 saved official primary-source evidence for pgvector 0.8.7, Qdrant 1.20.0 and
Pinecone's 2025-10 control-plane API. Hard gates are evaluated as `PASS`, `FAIL` or `UNKNOWN`; `UNKNOWN` never
becomes an implicit pass. Only eligible candidates are scored with weights frozen before results.

The provisional classroom choice is PostgreSQL + pgvector because it aligns with application-owned
transactional state and Exact/Flat. Its local-behavior score is zero: pgvector was not installed or run.
Qdrant and Pinecone remain visible with unresolved gates instead of being erased from the record.

```text
OFFICIAL_STATIC       = official docs/repository fact
DETERMINISTIC_FAKE    = state-machine and failure-boundary evidence
SIMULATED             = proposed behavior, not a product runtime
EXECUTED_LOCAL_RUNTIME= code actually executed locally
CONTROLLED_DATABASE_RUNTIME = real database started, exercised and stopped
PRODUCTION            = production evidence
```

The current evidence never reaches the last two levels.

## 8. Common Misconceptions

**Metric equivalence**

❌ Normalized cosine and dot product have similar ordering, so they are the same contract.

✅ Ordering equivalence does not preserve score values, threshold direction or database operators.

**ACK meaning**

❌ A `200` or accepted count proves the complete index generation.

✅ ACK is a candidate claim; exact correlation and authoritative readback are still required.

**Namespace security**

❌ Matching a tenant namespace is sufficient authorization.

✅ Namespace is physical routing. Current application grants remain authoritative.

**Filter ordering**

❌ Search broadly, then authorize only the returned top-k.

✅ Establish authorization scope first, constrain candidate generation, then recheck before return. Day100 owns
the complete retrieval/filter pipeline.

**Bigger ANN budgets**

❌ Maximum `ef_search` or `probes` is always best.

✅ Larger budgets may improve recall but cost latency and compute; the right value is workload evidence.

**Lease expiry**

❌ Once a lease expires, the old worker cannot write.

✅ Expiry is a time fact; fencing is the enforceable stale-writer rejection mechanism.

**Successful local tests**

❌ Green deterministic tests mean the database is production ready.

✅ They prove application invariants only. Real database, recovery, capacity and traffic evidence remain absent.

**Future retrieval terms**

`BM25` is a lexical ranking formula that rewards matching terms while adjusting for document length and term
rarity. Lexical+dense hybrid retrieval combines word matching with embedding similarity. A `reranker` is a
later, usually more expensive model or scoring stage that reorders a small candidate set. Human relevance
labels are judgments such as “relevant / not relevant” attached to query-document pairs for evaluation. These
belong to Day100/Day103, not the Day99 index build.

`model-v2 query encoder` means the exact model/revision and preprocessing used to turn a query into a vector.
It must be compatible with the document vector space. Merely naming it “v2” does not establish that contract.

A tie-break rule is the deterministic secondary ordering used when two scores are equal. Day99 uses point ID,
so repeated exact queries produce the same order.

## 9. Engineering Trade-offs

| Decision | Improves | Sacrifices / remaining risk |
|---|---|---|
| Exact/Flat first | correctness oracle, simple debugging | does not establish production scale |
| HNSW | fast graph traversal, strong recall potential | memory, build cost, approximate results |
| IVFFlat | tunable regional search, compact structure | training/centroid sensitivity, probe trade-off |
| Float32 exact | clean semantic baseline | larger memory than half precision |
| Dedicated tenant generation namespace | clear isolation and cleanup | more physical objects |
| Shared collection plus tenant predicate | lower object overhead | predicate omissions and side channels require fail-closed controls |
| Shadow generation | rollback window and consistent cutover | temporary duplicate storage/build cost |
| Application selected pointer | one authoritative cross-Provider model | requires projection/reconciliation with Provider aliases |
| Readback before seal | detects partial/extra/wrong content | extra I/O and eventual-consistency handling |
| Hard gates before weights | prevents unsafe popularity decisions | may leave no eligible production candidate |

The Tech Lead rejects in-place rebuilds, unversioned metric changes, global content-hash dedup across tenants,
raw vector logging, hidden epsilon policies and any design that makes a Provider filter the sole authorization
authority.

## 10. Hands-on Exercises

### Exercise 1: Translate score semantics

**Question:** Provider cosine distance is `0.18`; policy is similarity `>= 0.80`. What happens?

**Think First:** Identify direction and Adapter translation.

**Starter Artifact:** `similarity = 1 - distance`

**Expected Output:** `0.82`, accepted.

**Explanation:** The application compares its own similarity type, not the raw Provider distance.

**Follow-up Question:** Would exact `0.8000` pass an explicit `>` policy?

### Exercise 2: Classify parameter changes

**Question:** Classify HNSW `m`, `ef_construction`, `ef_search`, IVF `lists`, `probes` and threshold.

**Think First:** Does the value change stored topology or only query work?

**Expected Output:** `m`, `ef_construction`, `lists` require a new physical generation. `ef_search`, `probes`,
`top_k` and threshold require a new retrieval-policy revision and validation.

**Follow-up Question:** Why can a metric change not be treated like `top_k`?

### Exercise 3: Diagnose a partial write

**Question:** Three batches were sent; two ACKs arrived and readback contains four of five points.

**Think First:** Separate acknowledged, actual and durable application truth.

**Expected Output:** Reject activation, keep the generation inactive, record missing batch/point evidence, and
reconcile or abandon the orphan generation.

**Follow-up Question:** What changes if the third ACK was lost but readback proves all five exact points?

### Exercise 4: Design an upgrade

**Question:** Move from Flat to HNSW without interrupting G1.

**Think First:** Identify immutable facts, mutable pointer and CAS baseline.

**Expected Output:** Freeze a new contract, authorize and build G2 shadow, validate it, recheck current state,
then CAS G1 to G2 with Outbox in one application transaction. Retain G1 for the explicit rollback window.

**Follow-up Question:** Why can a delayed G1 event not reverse the pointer?

## 11. Relevant Framework Connections

**PostgreSQL + pgvector:** PostgreSQL transactions can own the application generation, pointer and Outbox.
pgvector operators and physical indexes remain behind an Adapter. RLS may add defense in depth but does not
replace the Day97 authorization decision. Real pgvector execution is not part of the saved classroom evidence.

**Qdrant:** Collections bind vector size and distance; points carry payload; filters, payload indexes, aliases,
snapshots and tenant strategies are relevant. Qdrant's atomic alias switch does not make an application DB and
Qdrant one distributed transaction, so reconciliation is still required.

**Pinecone:** API version, dimension, metric, namespace, cloud/region and record identity must be frozen.
Managed egress, retention, cost and recovery require explicit evidence. A namespace is routing, not a grant.

**FastAPI:** A future endpoint should read the selected bundle from application state, construct a compatible
query vector, apply current authorization and return application-owned result types. Day99 intentionally does
not add that endpoint.

## 12. AI Backend Connections

Day99 establishes the physical trust boundary beneath RAG:

```text
authorized source
  -> provenance-preserving chunks
  -> homogeneous document embeddings
  -> immutable selected vector generation
  -> authorized hybrid candidate retrieval (Day100)
  -> retrieval and answer evaluation (Day103)
```

Index correctness is not retrieval quality. Self-match, exact parity, recall@k and tenant-isolation probes show
whether coordinates were stored and searched as contracted. They do not show whether the chunks answer real
questions. Human relevance labels, reranking quality, grounding and answer quality are later evidence layers.

The side-channel risk also matters: even if forbidden rows are filtered out, shared latency, counts, cache keys
or error shapes may reveal another tenant's presence. Cache identity must include tenant, contract and
generation; metrics labels must remain low-cardinality and must never contain vectors or protected payload.

## 13. English Interview

**Key vocabulary:** exact nearest-neighbor search, approximate nearest neighbor, recall@k, score orientation,
shadow generation, selected pointer, fencing token, authoritative readback, reconciliation, hard gate.

**Beginner question:** What is the difference between a vector database and a vector index?

**Strong answer:** “A vector database owns durable records, metadata and operational APIs. A vector index is a
physical search structure such as Flat, HNSW or IVF. I keep application identity and score semantics outside
the database-specific representation.”

**Intermediate question:** How do you validate a partially acknowledged batch write?

**Strong answer:** “I correlate every ACK by request, batch, tenant, namespace, generation and point IDs. I do
not activate from ACKs. I read the shadow generation back, compare exact IDs and content-safe manifests, run
controlled probes, then recheck current authorization and lineage before the Committer can seal it.”

**Senior question:** How do you prevent a stale build from becoming current?

**Strong answer:** “The operation binds the current document, ChunkSet, EmbeddingSet, authorization revisions,
index contract and selection revisions. I build copy-on-write, use Committer-issued fencing, and re-read all
current facts immediately before commit. Activation is a CAS on the selected pointer with Outbox in the same
application transaction. Delayed events are classified against current state.”

**Common weak answer:** “I would upsert the vectors and switch the alias if the database returns success.”

Why it is weak: it omits current authorization, response correlation, readback, application authority,
unknown-outcome recovery, CAS and the evidence required to call a generation ready.

## 14. Mental Model Summary

```text
EmbeddingSet          = one immutable compatible vector space
VectorIndexContract   = physical storage/search meaning
RetrievalPolicy       = versioned query-time choices
Exact/Flat            = correctness oracle
ANN                    = recall/latency/memory trade-off
Batch ID              = stable write-correlation identity
Provider checkpoint   = opaque observed Provider-state marker
Manifest              = content-safe count/identity/vector/payload proof
Candidate             = proposal
Validator             = independent checker
Committer             = sole durable truth writer
Generation            = immutable history
Selected pointer      = mutable current fact
Outbox                = at-least-once notification hint
UNKNOWN               = reconcile; never blind replay
Fence                 = enforceable stale-writer rejection
```

## 15. Today's Takeaway

The most important mental model is that vector storage is a versioned, authorized publication workflow—not an
`upsert()` call. The most important production risk is plausible-looking but semantically incompatible or
cross-tenant results. The most important trade-off is Exact/Flat correctness versus ANN scale. The most
important framework boundary is that database-specific types and operators stop at the Adapter. The most
important interview answer is: ACKs and filters are evidence and defense in depth; they are not authorization,
application commit or production readiness.

The classroom generation is sealed but not activated because ANN, capacity, recovery and real Provider gates
remain `NOT_RUN`. That refusal is the intended result, not a failed lesson.

## 16. Before Next Lesson Checklist

- [ ] Can I explain vector database versus vector index without using product names?
- [ ] Can I translate distance to application similarity and preserve threshold direction?
- [ ] Can I explain why normalized cosine and dot-product ordering does not merge their contracts?
- [ ] Can I classify HNSW and IVF build/query parameters?
- [ ] Can I calculate and interpret recall@k without calling it answer quality?
- [ ] Can I explain why `chunk:read_for_embedding` does not authorize indexing?
- [ ] Can I list every identity used to correlate a Provider batch response?
- [ ] Can I explain ACK, checkpoint, readback and manifest as four different facts?
- [ ] Can I explain why timeout-after-dispatch requires reconciliation?
- [ ] Can I explain stable operation identity, fresh attempts and fencing together?
- [ ] Can I design a shadow generation and atomic selected-pointer cutover?
- [ ] Can I explain duplicate and delayed Outbox delivery?
- [ ] Can I distinguish `OFFICIAL_STATIC`, `DETERMINISTIC_FAKE`, `SIMULATED` and executed runtime evidence?
- [ ] Can I state which Day99 production gates remain `NOT_RUN`?
- [ ] Can I answer the senior interview question aloud in English?

Runnable checkpoint:

```sh
cd projects/ai-agent
PYTHONPATH=src:. python3.12 -m unittest discover -s tests -p 'test_day99_*.py' -q
PYTHONPATH=src:. python3.12 evals/run_day99_seed_eval.py
PYTHONPATH=src:. python3.12 examples/day99_vector_database_index_design.py
```
