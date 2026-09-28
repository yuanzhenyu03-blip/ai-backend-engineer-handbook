# Day96 — Chunking Strategy and Experiments (classroom draft)

This is a local classroom artifact, not a published lesson or a production-readiness
claim. It is based on remote `main` commit
`30eedfbf223283c59b8f81abb04606e3cb381359`. The implementation uses an
in-process teaching store and a deterministic classroom tokenizer.

## 1. Lesson Metadata

- Phase 7C, after Day95 ingestion and before Day97 metadata/ACL/provenance.
- Execution evidence: `EXECUTED_LOCAL_RUNTIME` for the Day96 teaching path.
- Production readiness: `MORE_EVIDENCE_NEEDED`.
- Formal repository publication is pending explicit instruction. The learner's
  independent synthesis and English Interview passed with recorded corrections.

## 2. Learning Objectives

Explain and test the difference among ParsedArtifact, ChunkSetCandidate,
immutable ChunkSet, and the selected ChunkSet pointer. Reproduce three bounded
strategies on one controlled input while preserving exact canonical-source
positions and failed experiment evidence.

## 3. Why This Matters

An answer can only cite a source accurately if a retrieved Chunk retains its
document/version identity and exact source positions. A cheaper or prettier
splitter does not establish retrieval quality. A partial or stale result must not
replace the selected set.

## 4. Roadmap Position

Day95 establishes an active immutable ParsedArtifact. Day96 derives immutable,
versioned ChunkSets. Day97 adds metadata and ACL enforcement; Day98 chooses
embedding models; Day99 builds an index; Day103 evaluates retrieval and answers.

## 5. Lesson Map

`Day95 eligibility → contract → tokenizer/strategy Adapter → candidate →
manifest/span/coverage/budget validation → sole Committer → immutable ChunkSet
→ conditional selection + outbox intent → Day97 handoff`.

## 6. Core Mental Model

Think of a ParsedArtifact as the verified edition of a book, a ChunkSet as one
numbered set of index cards made from that edition, and the selection pointer
as the publishing switch. A candidate is a proposed print run. Printing cards
does not activate a new edition or publish those cards.

## 7. Main Concepts

### Identity and ownership

The stable result identity binds tenant, document, immutable version, source,
ParsedArtifact, and the complete chunking contract. Attempt/request/generation
identify a fresh execution, so they do not enter the stable result key.
`chunk_index` is only an ordinal inside one set. Equal text/content hash at two
different source positions remains two logical Chunks.

### Tokenizer and budgets

`ClassroomTokenizer` groups ASCII word runs and counts other code points and
whitespace individually. It is deterministic, offline, and **not** a real
embedding-model tokenizer. `soft_target_tokens` guides size; `hard_max_tokens`
is a strict ceiling. Repeated heading/table context and overlap count toward
the ceiling. The contract also limits input/output size, Chunk count, work
units, estimated memory, and elapsed time. Work and memory values are
conservative estimates, not measured CPU or RSS guarantees.

### Boundaries and source positions

The fixed-window baseline cuts on token boundaries. Recursive mode prefers
section, paragraph, and sentence boundaries, followed by an explicit bounded
fallback. Section-aware mode additionally recognizes table rows and code
lines, and can repeat exact heading/table-header source segments. Its policy is
not a Markdown parser or code AST. `identity-v1` and
`collapse-horizontal-space-v1` normalization both retain a map to Day95
canonical-text offsets. These offsets are **not** original-file byte offsets.

### Validation and publication

The Adapter returns a candidate only. The validator reconstructs content from
the declared source segments and versioned normalization/join rules, verifies
hashes, token counts, source coverage, overlap, ordinals, and manifest binding.
The Committer rechecks Day95 authority, inserts one immutable ChunkSet under a
stable uniqueness key, and conditionally changes the selection pointer. The
selection change and pending outbox intent are one modeled in-process write.

## 8. Common Misconceptions

- `content_hash` cannot serve as tenant identity, authorization, or provenance.
- The presence of a complete B set does not mean B is selected; after a crash
  before pointer update, A remains current.
- An unselected valid B may be retained for audit. An invalid or partial B
  cannot be published.
- `Recall@k` does not replace the Day96 source-coverage check. A missing source
  span may be absent from all test questions.
- Fewer Chunks and lower overlap are cost/structure observations, not proof of
  better retrieval or answers.

## 9. Engineering Trade-offs

Fixed windows are simple and reproducible but can break semantic structure.
Structure-aware modes preserve more boundaries and context but consume extra
tokens and require explicit fallback when an atomic unit is oversized.
`FAIL_CLOSED` rejects an oversized unit; `BOUNDED_FALLBACK` records a smaller
boundary or a hard token split. No path may silently exceed the hard maximum.

## 10. Hands-on Exercises

Run the local classroom example and 16-case seed evaluator:

```bash
PYTHONPATH=projects/ai-agent:projects/ai-agent/src python3 \
  projects/ai-agent/examples/day96_chunking_experiments.py
PYTHONPATH=projects/ai-agent:projects/ai-agent/src python3 \
  projects/ai-agent/evals/run_day96_seed_eval.py
```

The `test_day96_chunking_core.py` suite covers Day95 gating, exact retries,
same-operation conflict, normalized offsets, repeated text at distinct spans,
context provenance, manifest/gap failures, stale attempts, stale Day95 active
pointer, concurrency, resource limits, and the safe example output. The
content-safe [experiment report](../evidence/day96-experiment-report.json)
retains three validated strategy runs and one rejected fail-closed run, each
with its exact contract. The
[validation record](../evidence/day96-validation.json) separates executed
local evidence from untested production requirements.

## 11. Relevant Framework Connections

A framework splitter may implement the computation behind an Adapter. Its
private `Document` or tokenizer types must not become the application's Chunk
contract or obtain direct durable-write authority. The current example uses no
framework dependency or model Provider.

## 12. AI Backend Connections

Day97 receives immutable tenant/document/version/source/parsed-artifact
bindings, ChunkSet and Chunk identities, content checksums, and exact source
segments. ACL decisions belong to Day97; `tenant_id` alone is not a grant.
Day98 may generate multiple embedding versions from one unchanged ChunkSet.
Day103 must use question labels anchored to source evidence rather than to one
strategy's `chunk_id`. Even within one tenant, two principals with different
ACL visibility cannot automatically share one accessible gold-evidence set.
The source evidence and the evaluating principal's authorized view are
separate inputs; Day97 enforces that view.

## 13. English Interview

Learner practice covered beginner distinctions (ParsedArtifact/ChunkSet,
`chunk_index`, overlap, characters/tokens), intermediate provenance,
re-ingestion/re-chunking, oversized fallback, and evaluation boundaries, plus
senior experiment comparison, stale selection, citation lineage, Adapter
ownership, and missing production evidence. Assessment:
`PASS_WITH_TECHNICAL_AND_LANGUAGE_CORRECTIONS`.

Representative weak answer: “Overlap avoids a missing source span.” Corrected
strong answer: “Overlap preserves context across boundaries, but independent
source-coverage validation detects gaps.” The learner then correctly rejected
the idea that overlap elsewhere repairs offsets 700–750.

Representative weak answer: “Re-ingestion happens when stable identity
changes; re-chunking makes a new parsed artifact.” Corrected strong answer:
“Changed source content or parser contract goes through Day95 re-ingestion,
usually creating a new DocumentVersion. A changed chunking contract uses the
same active ParsedArtifact and creates a new immutable ChunkSet.” The learner
correctly classified a parser-contract change as re-ingestion.

For the senior case, the learner identified atomic conditional selection and
generation fencing, then correctly rejected an unconditional retry after zero
updated rows. The final answer separated structural metrics from retrieval
evaluation with labeled questions, authorized gold evidence, and actual
retrieval results. Language corrections included `immutable`, `receive`, and
“does not prove” in place of “can't instead of.”

## 14. Mental Model Summary

`DocumentVersion` changes only through Day95 ingestion. Changing a strategy,
tokenizer, normalization, or relevant configuration creates a new immutable
ChunkSet. A selection proposal is not a durable selection. A stale attempt or
changed Day95 active version cannot publish its result.

## 15. Today's Takeaway

First prove the source is eligible; then make every boundary reproducible and
traceable; finally publish one complete set with a guarded pointer update.

## 16. Before Next Lesson Checklist

- Confirm the controlled experiment report and its failed cases are retained.
- Consult the [research evidence](../research/day96-chunking-evidence.jsonl)
  before choosing a real tokenizer or external splitter; neither was executed.
- Keep original canonical-text offsets, not invented original-file byte offsets.
- Re-run the Day95 dependency and MCP runtime regressions after final edits.
- Record missing production evidence: real tokenizer, durable transactional
  store, multi-process fencing, crash/restart recovery, telemetry, load/soak,
  and downstream retrieval/answer evaluation.
- Preserve the learner's independent synthesis and English Interview
  corrections in the local validation record; neither is a production claim.
