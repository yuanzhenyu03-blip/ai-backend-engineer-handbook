# Day 96 — Chunking Strategy and Experiments

## 1. Lesson Metadata

- Status: ✅ Completed at guided classroom scope
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced
- Estimated study time: 6–8 hours
- Prerequisites: Day49, Day50, Day57, Day64, Day71–73, Day77, Day82, Day86, Day94 and Day95
- Previous lesson: [Day95 — RAG Ingestion](day95-rag-ingestion-pipeline-parsing-and-document-lifecycle.md)
- Next lesson: Day97 — Metadata, Tenant, ACL and Provenance
- Main artifact: [Day96 application-owned design](../../projects/ai-agent/docs/DAY96_CHUNKING_STRATEGY_EXPERIMENTS.md)
- Runnable example: [Controlled strategy comparison](../../projects/ai-agent/examples/day96_chunking_experiments.py)
- Experiment report: [Four retained attempts](../../projects/ai-agent/evidence/day96-experiment-report.json)
- Validation: [Day96 local evidence](../../projects/ai-agent/evidence/day96-validation.json)
- Evidence level: `EXECUTED_LOCAL_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After this lesson, the learner can:

- explain why a Day95 active ParsedArtifact is eligible source content but is not yet a retrieval unit;
- distinguish an operation, attempt, experiment, candidate, immutable ChunkSet and selected pointer;
- defend contract-derived identity instead of reusing an ordinal or content hash;
- implement and compare fixed-token, recursive and section-aware strategies on one controlled corpus;
- calculate token budgets, overlap and exact canonical-source coverage without conflating them;
- validate normalization maps, source segments, hashes, manifest, lineage and hard limits;
- reject stale candidates and update selection only through a conditional Committer;
- interpret structural metrics without claiming retrieval or answer quality;
- state Day97 authorization and Day98–Day103 dependency boundaries in English.

## 3. Why This Matters

A verified document may be too large for a model context or a useful retrieval unit. A careless split can
separate a table row from its header, cut a function in half, omit a paragraph or make citations point to the
wrong repeated sentence. If a new experiment overwrites old chunk rows, existing embedding, index and citation
evidence may silently change meaning. If a stale worker changes selection after Day95 activates a new document
version, downstream consumers can process the wrong source. These are reliability, cost, security and audit
problems—not just text-formatting problems.

Day96 makes chunk boundaries reproducible and traceable before Day97 adds the complete ACL/provenance layer,
Day98 selects an embedding tokenizer/model, Day99 indexes, and Day103 evaluates retrieval and answers. Its
single synthetic corpus and classroom tokenizer are intentionally bounded evidence.

## 4. Roadmap Position

```text
Day49 verified upload → Day50 idempotency/outbox → Day57 failure injection
       ↓
Day64 extraction evidence → Day71 token budget → Day72–73 replaceable/versioned Adapter
       ↓
Day77 regression → Day82 recovery → Day86 untrusted-data boundary
       ↓
Day94 candidate → validation → sole Committer
       ↓
Day95 ACTIVE DocumentVersion + immutable ParsedArtifact
       ↓
Day96 versioned ChunkSets + controlled experiments + selected pointer
       ↓
Day97 ACL/provenance → Day98 embedding → Day99 index → Day103 evaluation
```

Day96 reuses Day95 document truth. It neither re-parses the upload nor creates a new DocumentVersion when only
the chunking strategy changes. Later RAG stages need stable ChunkSet and source identities before they can
index, authorize or cite anything.

## 5. Lesson Map

```text
active-version eligibility
→ protected ParsedArtifact binding/checksum
→ operation + fresh attempt + experiment + versioned contract
→ bounded Tokenizer/Strategy Adapter
→ ChunkSetCandidate
→ manifest/span/coverage/overlap/token/provenance validation
→ sole Committer inserts immutable ChunkSet
→ independent selection proposal
→ conditional selected-pointer update + outbox intent
→ Day97 handoff
```

Cancellation, deadline, capacity, chunk-count, input/output, estimated-memory and token-work limits run across
the path. A failed or unselected experiment remains evidence; it is not silently turned into production truth.

## 6. Core Mental Model

Think of the Day95 ParsedArtifact as a verified edition of a book. A ChunkSet is one numbered set of index
cards cut from that edition under a specified rule. Another rule makes a **different** set of cards without
changing the book. `chunk_index` is merely the card number *inside one set*. The selection pointer is a
publishing switch, not a new book edition or an authorization grant.

```text
ParsedArtifact(v2)
  ├─ experiment A: fixed-token-v1      → immutable ChunkSet A ← selected
  ├─ experiment B: section-aware-v2    → immutable ChunkSet B ← valid candidate
  └─ experiment C: fail-closed limit   → rejected evidence

Only the Committer may atomically change selected A → B.
Old A remains intact. Day95 active version must still be v2.
```

## 7. Main Concepts

### Concept 1: Eligibility is inherited, not recreated

#### Tech Lead Question

Can a parser success response, a registered version, or a matching filename enter Day96?

#### Student Thinking and Answer

The learner chose the strict gate: “先建立‘只能接收 Day95 已激活、有效的 ParsedArtifact’的 eligibility gate.”
They later corrected a tempting shortcut: changed source or parser contract must go back through Day95, not
be disguised as re-chunking.

#### Tech Lead Review

Day95 must already have committed `Document.state == ACTIVE`, the exact `active_version_pointer`, an ACTIVE
DocumentVersion with a parsed-artifact ID, and a COMPLETED ingestion operation. Day96 additionally checks
tenant/document/version/source/operation lineage, source checksum, parsed checksum and ParseManifest. The
ParsedArtifact is verified content; activation does **not** authorize it to every principal. Current access
must be checked before protected content is used, and Day97 owns the complete ACL subsystem.

#### Engineering Thinking and Production Example

After v3 becomes active, a completed v2 ChunkSet remains audit evidence but is not current for v3. The
Committer rejects a v2 selection update. A reader must compare the selected set's version with Day95's
current active version rather than follow an old pointer blindly.

#### Framework Connection and Exercise

Object Storage keys and parser-private objects cannot substitute for Day95 application lifecycle facts.
Exercise: a parser returned success but the ingestion operation is `PENDING_RECONCILIATION`. Is Day96 eligible?
No; parser output is still a candidate, and Day96 creates no activation fact.

### Concept 2: ChunkSet identity and immutable experiment history

#### Tech Lead Question

May structure-aware B overwrite A's rows and reuse A's `chunk_id` or `chunk_index`?

#### Student Thinking and Answer

The learner rejected overwriting because “每个 experiment 应该保留 owner 的 result”; the two sets bind different
contracts/tokenizers, and even identical text can have different source spans and indices. They kept A selected
while B remained a valid unselected candidate.

#### Tech Lead Review

An operation binds the Day95 version/source/ParsedArtifact, an idempotency key and the full chunking-contract
fingerprint. A fresh attempt changes attempt number, request ID and generation but not that stable result
identity. An experiment records the hypothesis, exact contract and metrics. `ChunkSetCandidate` has no durable
authority. The sole Committer inserts an immutable ChunkSet under a stable uniqueness key; an exact retry
returns the existing result. Same operation with changed contract is an identity conflict or a new explicit
experiment. A changed tokenizer/strategy/configuration creates a new ChunkSet, not a new DocumentVersion.

`chunk_index` expresses local order, not global identity. Equal chunk text hashes prove byte equality only;
they do not prove tenant, version, source position or authorization. Two identical sentences at different
offsets remain distinct chunks with different provenance. Chunk identity binds the set and source segments.

#### Engineering Thinking and Production Example

Old A may already be referenced by embedding or citation evidence. Keeping immutable A makes those references
auditable when B changes boundaries or count. The trade-off is retained storage; overwriting would cost
correctness and rollback evidence. The classroom store models conditional insertion; a production database
needs actual unique constraints, transactions and restart tests.

#### Framework Connection and Exercise

A text-splitting library may compute a candidate behind an Adapter. Its private `Document`/node/tokenizer
types and `start_index` are not application identity or Committer authority. Exercise: two sections contain
the same sentence. Can a shared content hash merge them? No; citation would lose the source occurrence.

### Concept 3: Budget, boundary, normalization and exact provenance

#### Tech Lead Question

How do we keep a paragraph, table or function readable without silently exceeding the hard token limit?

#### Student Thinking and Answer

The learner distinguished soft from hard: “soft 只是期望达到值不是硬指标.” They preferred cutting between functions,
noticed repeated table headers consume tokens, and asked whether every chunk should carry a header. They also
insisted a missing interval be “标注在原始 `ParsedArtifact` 的来源位置上” and rejected using overlap to hide a gap.

#### Tech Lead Review

A token count depends on a versioned tokenizer; character count is not a substitute. The soft target guides
normal chunk size, while the hard maximum includes body, overlap and repeated heading/table-header context.
Fixed-token splitting provides a baseline. Recursive splitting prefers section → paragraph → sentence →
whitespace → explicit hard-token fallback. Section-aware mode also recognizes table rows and code lines. An
oversized atomic unit either fails closed or follows a versioned, bounded fallback with a recorded reason.

Every chunk records ordered source segments into Day95 **canonical parsed text**, including separate heading
or table-header segments where repeated. Normalization is versioned and maps back to canonical offsets; these
are not original uploaded-file byte offsets. The validator reconstructs text from segments and join rules,
checks hashes/counts/manifest, rejects empty or out-of-range spans, and checks full coverage and permitted
overlap. Intentional overlap repeats an interval for context; it does not repair an uncovered interval.

#### Engineering Thinking and Production Example

For a large table, carrying a header can improve row interpretation but consumes budget. A whole-table
chunk may exceed the hard limit; splitting rows requires exact row/header spans. Code is cut between functions
when possible, but this classroom Markdown-like policy is not a parser or AST. A real deployment needs tests
against its own document types and tokenizer.

#### Framework Connection and Exercise

The deterministic `ClassroomTokenizer` tests application control flow without downloading model data. It
does not prove a production model's token count. Exercise: the canonical source has a gap at offsets 700–750.
Can overlap elsewhere make coverage pass? No; a body source span must actually cover that interval.

### Concept 4: Selection, fencing and outbox

#### Tech Lead Question

Two workers finish B at nearly the same time. Can either write selected B after Day95 changes active v2 → v3?

#### Student Thinking and Answer

The learner proposed “原子性有条件的更新，update set returning”; zero returned rows converge to the already
selected set or reject. They also insisted an invalid new strategy leaves the production pointer unchanged,
and that dispatch intent be saved in the same transaction before notification.

#### Tech Lead Review

The Committer compares the claim attempt/generation/fence, expected selection ID/revision and Day95 active
state/version/fence. Only one conditional update may win. A zero-row outcome is not permission for an
unconditional retry. The selected pointer and outbox intent are one modeled write; notification is a wake-up
hint, never authority. Duplicate delivery is possible, so downstream effects need idempotency and a fresh
read of the authoritative pointer. A valid but stale B can remain evidence; A stays selected. If Day95 is now
v3, A is historical v2 evidence and cannot be served as current v3 knowledge.

#### Engineering Thinking, Framework Connection and Exercise

The in-process lock demonstrates the decision sequence, not distributed atomicity or crash recovery. A
production Committer needs one durable conditional transaction and outbox delivery tests. Exercise: a worker
updates zero rows. May it retry unconditionally? No; inspect current authority, converge if the same result
already won, otherwise reject with evidence.

### Concept 5: Experiments are comparisons, not retrieval evaluation

#### Tech Lead Question

If B has fewer chunks than A, has B won?

#### Student Thinking and Answer

The learner initially did not know how to compare strategies without cherry-picking. They then correctly
rejected ranking a candidate with 2% source gap, and distinguished `MRR`, `Precision@5` and `Recall@5` from
the Day96 structural gates. They noted that `MRR` has boundaries and must be combined with other metrics.

#### Tech Lead Review

Freeze one corpus and input, predeclare hard acceptance gates and comparison metrics, run all strategies,
save full contracts and all outcomes (including failures), rerun deterministically, then explain the
selection's trade-off and uncertainty. In the controlled report, fixed-token produced 9 chunks, recursive
10, section-aware 11; all three valid runs had full coverage and zero gaps. A fourth strict policy was
rejected for `OVERSIZED_ATOMIC_UNIT`. The section-aware set was selected for its controlled structural
preference, **not** proven universally best. Fewer chunks can lower cost while harming boundaries.

Day96 coverage checks whether all canonical source is represented. Retrieval `Recall@k`/`Precision@k` need
labeled questions, authorized gold evidence and actual retrieved rankings; MRR captures rank of the first
relevant result but is not sufficient alone. Day103 owns formal retrieval and answer evaluation.

#### Engineering Thinking, Framework Connection and Exercise

Use a content-safe experiment report with contract fingerprint, exact contract, checksums and aggregate
metrics—not raw customer text. A semantic splitter that needs embeddings is a future Day98 candidate, not a
Day96 runtime dependency. Exercise: B has fewer chunks but 98% coverage. Reject it before cost ranking.

## 8. Common Misconceptions

| Tempting belief | Correct engineering model | Memory cue |
|---|---|---|
| A parser response makes content eligible | Only Day95 Committer-activated version and parsed artifact do | Candidate ≠ fact |
| Re-chunking changes DocumentVersion | Same active ParsedArtifact + changed chunk contract → new ChunkSet | New cards, same book |
| Same text hash means same chunk | Different source spans remain distinct | Equality ≠ provenance |
| `chunk_index` is stable across strategies | It is local order inside one immutable set | Index ≠ ID |
| Overlap prevents missing source content | Coverage is independently checked | Shared context ≠ full coverage |
| Soft target is a hard ceiling | Hard max is strict; soft target is preference | Aim vs fence |
| Selected pointer authorizes retrieval | Check active version and principal ACL separately | Pointer ≠ permit |
| Fewer chunks or 100% coverage proves retrieval | Day103 needs labeled queries and actual results | Structure ≠ relevance |

These beliefs are plausible because many splitter APIs expose only chunks, lengths and overlap. The
application must add stable identity, provenance, eligibility, validation and authority boundaries.

## 9. Engineering Trade-offs

| Choice | Benefit | Cost / when to choose differently |
|---|---|---|
| Fixed-token baseline | Simple, reproducible control | May cut semantic units; compare with structure-aware modes |
| Recursive boundaries | More readable paragraphs/sentences | Fallback and language-specific punctuation need explicit testing |
| Repeated heading/table header | Better local context | Extra tokens/storage and possible retrieval duplication |
| `FAIL_CLOSED` oversized policy | Strong boundary guarantee | Rejects usable content; bounded fallback may be preferable if citations remain exact |
| Immutable experiments | Audit, reproducibility, safe rollback | More storage; retention must be planned |
| In-memory modeled transaction | Fast deterministic classroom tests | No multi-process durability/fencing evidence |

A Tech Lead should reject any choice that silently drops source text, exceeds the hard ceiling, erases a prior
experiment, treats content hash as permission, or presents one-corpus structural metrics as search quality.

## 10. Hands-on Exercises

### Exercise 1: Run one controlled corpus through three strategies

Question: Which strategies pass the hard gates, and what do their chunk counts actually prove?

Think First: Fix the same Day95 active ParsedArtifact and contract dimensions other than strategy.

Starter Artifact: [Example](../../projects/ai-agent/examples/day96_chunking_experiments.py).

Expected Output: Three validated runs, one rejected fail-closed run, complete structural metrics, one
selected set and one outbox intent; no raw source text in the report.

Explanation: Counts and boundary rates are observations, not a retrieval-quality verdict.

Follow-up Question: Would the result generalize to a different tokenizer or corpus? No.

### Exercise 2: Try a forged candidate

Question: Can a candidate repeat an earlier body span and still be committed because the union covers all
source offsets?

Think First: Check ordered body progress, explicit overlap, source reconstruction and manifest checksum.

Starter Artifact: [Day96 tests](../../projects/ai-agent/tests/test_day96_chunking_core.py).

Expected Output: `SOURCE_SPAN_INVALID`, zero new ChunkSet and no selection change.

Explanation: A coverage ratio alone cannot certify that every chunk has valid provenance.

Follow-up Question: Why must the validator be independent of the strategy Adapter? The Adapter's output is a
candidate, and it cannot certify its own authority.

### Exercise 3: Reject a stale selection

Question: A was selected for v2; B finished after Day95 activated v3. What state survives?

Think First: Keep the old set for audit, then compare active version, selection revision and fence.

Starter Artifact: [Committer](../../projects/ai-agent/src/rag_chunking_committer.py).

Expected Output: B cannot become current; A remains historical; v3 needs its own eligible set.

Explanation: Pointer persistence and current-reader eligibility are distinct facts.

Follow-up Question: What must a downstream consumer do after a duplicate notification? Read current
authority and apply its own idempotency key.

## 11. Relevant Framework Connections

[LangChain TextSplitter](https://reference.langchain.com/python/langchain-text-splitters/base/TextSplitter)
exposes size, overlap, a length function and optional start index; that does not establish this application's
full Day95 lineage, multiple exact source segments, manifest or commit authority. [LlamaIndex node parsers](https://docs.llamaindex.ai/en/v0.10.22/module_guides/loading/node_parsers/modules/)
illustrate sentence/code-aware and embedding-based semantic alternatives. Neither framework was executed in
Day96. If one is later selected, pin its version and translate its private objects behind an Adapter. The
application still owns candidate validation and Committer authority. The research basis and version caveats
are recorded in [Day96 source evidence](../../projects/ai-agent/research/day96-chunking-evidence.jsonl).

## 12. AI Backend Connections

Day97 must evaluate each requesting principal's ACL before protected chunk text is exposed. Same tenant is
necessary but not sufficient; gold evidence labels for evaluation are anchored to source positions and must
be scoped to the principal's authorized view. Day98 may create multiple embedding versions from one unchanged
ChunkSet. Day99 indexes a selected, eligible set; delayed outbox delivery must not resurrect an old pointer.
Day102 citations follow canonical source spans, not a cross-strategy `chunk_index`. Day103 evaluates actual
retrieval and answer results. Untrusted document text, including prompt-like content, remains data rather than
instruction authority. Telemetry may aid diagnosis but cannot authorize or commit.

## 13. English Interview

Key vocabulary: *immutable*, *source span*, *overlap*, *hard limit*, *soft target*, *candidate*, *fence*,
*selected pointer*, *provenance*, *retrieval quality*.

Beginner — “What is the difference between a ParsedArtifact and a ChunkSet?”

> A ParsedArtifact is verified parsed content associated with an active DocumentVersion. A ChunkSet is an
> immutable collection of chunks derived from it under a versioned chunking contract.

Intermediate — “What is the difference between re-ingestion and re-chunking?”

> Changed source content or parser contract goes through Day95 re-ingestion. A changed chunking contract
> creates a new ChunkSet from the same active ParsedArtifact, not a new DocumentVersion.

Senior — “How do you keep a stale experiment from replacing the selected set?”

> The Committer rechecks the active version and uses an atomic conditional update against the expected
> selection revision and claim fence. A losing worker keeps evidence and does not retry unconditionally.

Common weak answers heard in class included “a ChunkSet is an inmutable set,” “overlap avoids missing source
spans,” and “re-ingestion happens when stable identity changes.” The learner corrected these after feedback:
the set is *immutable and provenance-bound*; overlap preserves context but coverage detects gaps; stable
logical document identity survives re-ingestion. A strong production answer also names what is **not proven**:
real model token counts, distributed durable fencing, current ACL enforcement and retrieval quality.

## 14. Mental Model Summary

```text
ParsedArtifact        = Day95 validated content, not a retrieval unit or universal permit
ChunkSetCandidate     = proposed split with no durable authority
ChunkSet              = immutable, contract-bound set with exact source lineage
chunk_index           = local order; chunk_id = set/provenance-bound identity
content hash          = byte equality, not source identity or ACL
soft target           = sizing preference; hard max = strict limit
overlap               = intentional context duplication, not coverage repair
selected pointer      = guarded publishing signal, not authorization
structural metrics    = Day96 evidence, not Day103 retrieval evaluation
```

## 15. Today's Takeaway

First prove the source is Day95 eligible; then make every boundary, token count and source span reproducible;
finally let the sole Committer persist immutable results and guard selection. The most dangerous shortcuts
are overwriting old chunks, confusing overlap with coverage, treating a pointer as authorization, and
describing a tidy structural experiment as retrieval quality. A library can help compute splits behind an
Adapter, but it cannot own the application's lineage or publication authority.

## 16. Before Next Lesson Checklist

- [ ] Can I state the exact Day95 active-version eligibility predicate?
- [ ] Can I distinguish re-ingestion from re-chunking without changing logical document identity?
- [ ] Can I explain operation, attempt, experiment, candidate, committed set and selection pointer?
- [ ] Can I explain why equal text/hash or equal `chunk_index` does not establish identity?
- [ ] Can I reconstruct each chunk from exact canonical ParsedArtifact source segments?
- [ ] Can I keep soft target, hard maximum, overlap and coverage as separate checks?
- [ ] Can I explain fail-closed versus explicit bounded fallback for a table or paragraph?
- [ ] Can I compare all controlled experiments without hiding rejected cases?
- [ ] Can I keep a stale worker from changing selection and retain its evidence?
- [ ] Can I name what the classroom tokenizer and in-memory store do **not** prove?
- [ ] Can I explain Day97 ACL and Day103 retrieval evaluation boundaries in English?
