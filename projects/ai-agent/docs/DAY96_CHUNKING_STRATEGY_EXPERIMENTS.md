# Day96 Chunking Strategy and Experiments — Application Contract

Day96 consumes only the [Day95](DAY95_TO_DAY96_HANDOFF.md) Committer-activated immutable ParsedArtifact. It
produces candidate and committed ChunkSets but never creates or changes a DocumentVersion. This document is
the implementation contract for the bounded local classroom path, not a production-readiness statement.

## Authority and lifecycle

```text
Day95 ACTIVE document + exact active version + COMPLETED ingestion
        ↓ protected read, source/parse manifest and checksum validation
Day96 stable operation + idempotency key + versioned ChunkingContract
        ↓ fresh attempt/request/generation + deadline/capacity preflight
conditional claim / CHUNKING_STARTED marker (in-process model)
        ↓ TokenizerPort + Strategy Adapter
ChunkSetCandidate
        ↓ independent manifest/span/coverage/overlap/token validation
sole ChunkSet Committer
        ├─ immutable ChunkSet insert or exact-duplicate convergence
        └─ separate conditional selection + outbox intent
        ↓
Day97 eligible selected identity, subject to active-version and ACL checks
```

The pure Adapter cannot write a set. The experiment runner can evaluate and propose but cannot select. The
validator has zero Committer calls. The sole Committer rechecks current Day95 facts under a modeled shared
lock before insertion/selection; this is **not** a distributed transaction.

## Immutable and fresh identities

| Scope | Binding | Rule |
|---|---|---|
| Day95 input | tenant, logical document, immutable version, source artifact, ParsedArtifact, ingestion operation and ParseManifest | Must be current and exact |
| Stable result | Day95 identity + full chunking-contract fingerprint | Unique set key; exact retry converges |
| Operation | stable operation ID and idempotency key | Same ID with changed contract conflicts |
| Attempt | attempt number, request ID and generation | Fresh execution; stale generation is fenced |
| Experiment | experiment ID, hypothesis, corpus, contract, results and uncertainty | Preserve validated and rejected attempts |
| ChunkSet | result key, manifest and ordered immutable chunks | Never overwrite old rows |
| Chunk | set ID, ordinal and exact source segments | Equal text/hash does not merge occurrences |
| Selection | document key, selected set ID, revision and fence | Independent guarded fact |

The complete contract records strategy name/version, tokenizer name/version, normalization and boundary-policy
versions, soft/hard/min sizes, overlap, oversized policy and resource budgets. A strategy/tokenizer/relevant
configuration change creates a new ChunkSet under the same Day95 ParsedArtifact. Changed source bytes or
parser contract instead returns to Day95 re-ingestion.

## Eligibility and candidate validation

The input predicate is:

```text
Document.state == ACTIVE
AND Document.active_version_pointer == DocumentVersion.document_version_id
AND DocumentVersion.state == ACTIVE
AND DocumentVersion.parsed_artifact_id IS NOT NULL
AND IngestionOperation.state == COMPLETED
```

In addition, the path verifies tenant/document/version/source/operation identities, current Day95 source and
parsed-artifact references, source and output checksums, ParseManifest lineage, parser contract/attempt
correlation and the full Day96 contract fingerprint. REGISTERED, QUARANTINED, TOMBSTONED, SUPERSEDED, stale,
pending-reconciliation and candidate-only inputs are ineligible. `filename`, object key, content hash and
telemetry cannot replace these facts.

`ChunkSetCandidateValidator` independently checks:

- operation/attempt/experiment correlation, manifest count and checksum;
- exact reconstruction from ordered canonical-source segments plus versioned normalization/join rules;
- body progress and full source coverage, rejecting gaps and unintended repeated body ranges;
- actual token count, hard maximum, minimum size, output size and maximum chunk count;
- adjacent body overlap against the explicit contract and separate context-segment roles;
- source/parsed checksum and lineage again before Committer insertion.

Source offsets are Python string positions in Day95 canonical parsed text, **not** source-object byte offsets.
Each repeated heading or table header is an explicit source segment. Citation consumers can reconstruct which
occurrence was used, including when two sections contain identical text.

## Controlled strategies and budgets

`ClassroomTokenizer` deterministically groups ASCII word runs and counts other code points/whitespace as
separate tokens. It is dependency-free and offline. Its count is not a real embedding-model count.

| Strategy | Preferred boundary | Important trade-off |
|---|---|---|
| Fixed-token | Token window | Reproducible baseline; may break structure |
| Recursive | Section → paragraph → sentence → whitespace/hard fallback | Better readable boundaries, simple heuristics |
| Section-aware | Section → paragraph → table row/code line → sentence → bounded fallback | Retains heading/table context at extra token cost |

`soft_target_tokens` is a preference. `hard_max_tokens` is absolute and includes repeated context. An
oversized paragraph/row either raises `OVERSIZED_ATOMIC_UNIT` under `FAIL_CLOSED` or records a bounded fallback
reason. The contract also bounds input/output chars, chunk count, token work units, estimated memory and
elapsed time. Work/memory are estimates, not measured CPU/RSS or a production resource guarantee. The
Markdown-like boundary heuristic is neither a full parser nor an AST; multilingual sentence segmentation is
not Unicode UAX #29 conformance.

## Selection, outbox and stale results

The Committer first inserts immutable chunks under a stable unique result key. Selection is a separate CAS
against expected pointer/revision, Day95 state version/fence and current claim fence. A zero-row/conflicting
result cannot become an unconditional retry. Same-result retries converge; other stale attempts are rejected
with reason and their prior experiment evidence remains available. The in-memory selection mutation and
outbox intent insertion share one modeled critical section. The intent is saved before dispatch and is only a
wake-up hint. Delivery can repeat; a downstream consumer must re-read the authoritative pointer, match its
document version to Day95 current active version, check current authorization, and use its own idempotency key.

A valid unselected B does not replace selected A. An invalid B never becomes a set. If Day95 advances to v3,
A is retained as v2 history but is not eligible current input for v3. Day96 never changes Day95 lifecycle.

## Experiment and evidence

The [deterministic example](../examples/day96_chunking_experiments.py) runs three valid strategies and one
fail-closed contract against one synthetic corpus containing headings, paragraphs, list, repeated text,
Unicode/Chinese/English, table, code and prompt-like untrusted data. The [saved report](../evidence/day96-experiment-report.json)
retains the full contract, safe reason and structural metrics for every attempt, including the rejection.
The [seed](../evals/day96_chunking_seed.jsonl) has 16 controlled cases. The selected section-aware run is a
classroom structural preference, not a universal winner.

Coverage, gap, token counts, boundary-breaks, overlap ratio and deterministic rerun are Day96 structural
evidence. `Recall@k`, `Precision@k`, MRR and answer quality require labeled, authorized gold source evidence
and actual downstream retrieval/answer outputs; those are future Day103 evaluation, **NOT RUN** here. One
principal's ACL-filtered gold set cannot automatically be reused for another principal.

## Reproduce and review

From the repository root with the project on `PYTHONPATH`:

```bash
PYTHONPATH=projects/ai-agent:projects/ai-agent/src python3 \
  projects/ai-agent/examples/day96_chunking_experiments.py
PYTHONPATH=projects/ai-agent:projects/ai-agent/src python3 \
  projects/ai-agent/evals/run_day96_seed_eval.py
PYTHONPATH=projects/ai-agent:projects/ai-agent/src python3 \
  -m unittest discover -s projects/ai-agent/tests -p 'test_day96_*.py' -q
```

The classroom executed Python 3.11.5, not the preferred Python 3.12+. The [validation record](../evidence/day96-validation.json)
reports 25/25 focused tests, 16/16 seed and 674/674 available Day-series regression tests, with
`EXECUTED_LOCAL_RUNTIME` evidence and `MORE_EVIDENCE_NEEDED` production readiness. The [research record](../research/day96-chunking-evidence.jsonl)
documents current official library/specification observations; no real tokenizer, external splitter,
embedding provider, vector index or production document was run.

## Day97 handoff and remaining production work

See the [Day97 handoff](DAY96_TO_DAY97_HANDOFF.md). Day97 must apply current principal ACL/metadata policy;
tenant equality or a selected pointer alone is not authorization. Production still needs a fixed real
model-specific tokenizer, durable transactional set/selection/outbox storage, multi-process fencing and
restart recovery, real dispatch/deduplication, measured CPU/RSS/load/soak behavior, telemetry/alert delivery,
document-type/language coverage, and later retrieval/answer evaluation. Day96 deliberately does not implement
those future stages.
