# Day 95 — RAG Ingestion Pipeline, Parsing and Document Lifecycle

## 1. Lesson Metadata

- Status: ✅ Completed at guided classroom scope
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Advanced
- Estimated study time: 6–8 hours
- Prerequisites: Day49, Day50, Day57, Day64, Day82, Day86 and Day94
- Previous lesson:
  [Day94 — Agent + MCP Integration Capstone](day94-agent-mcp-integration-capstone-and-english-interview.md)
- Next lesson: Day96 — Chunking Strategy and Experiments
- Main engineering artifact: [Day95 RAG ingestion design](../../projects/ai-agent/docs/DAY95_RAG_INGESTION.md)
- Runnable example: [Deterministic ingestion](../../projects/ai-agent/examples/day95_rag_ingestion.py)
- Validation evidence: [Day95 validation](../../projects/ai-agent/evidence/day95-validation.json)
- Day96 handoff: [Validated input contract](../../projects/ai-agent/docs/DAY95_TO_DAY96_HANDOFF.md)
- Evidence level: `INTEGRATION_RUNTIME`
- Production readiness: `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After this lesson, the learner can:

- explain RAG ingestion in plain language before discussing chunking or vector search;
- distinguish filename, object key, source artifact, logical document, immutable document version,
  ingestion operation, parser attempt and parsed artifact;
- validate untrusted bytes without treating extension or request MIME as authority;
- keep parser-private types behind an Adapter and treat every parser result as a candidate;
- design a parse manifest that binds source, document, parser and attempt evidence;
- persist a dispatch marker before parser handoff and reject stale worker/generation results;
- activate a version only through one guarded Ingestion Committer;
- distinguish exact duplicate, identity conflict, re-ingestion, supersede, quarantine and tombstone;
- recover from timeout and eventually consistent `NOT_FOUND` without blind parser replay;
- retry only after authoritative non-execution is durably committed;
- state exactly what Day96 may accept;
- defend the architecture and its production gaps in English.

## 3. Why This Matters

Uploading a file does not create trustworthy knowledge. A filename can be changed, request MIME can be
spoofed, bytes can be malformed, a parser can return output for the wrong attempt, and a worker can crash
after the parser has already produced an artifact. If an application immediately chunks whatever a parser
returns, it can publish stale, cross-tenant, unsafe or untraceable knowledge.

Day95 establishes document truth before retrieval work begins. It answers:

- Who owns this logical document?
- Which immutable version is being processed?
- Which exact bytes were admitted?
- Which parser contract and attempt produced this candidate?
- Did the application validate and durably activate it?
- Can timeout recovery proceed without duplicating parser work?
- Which evidence must remain after quarantine, supersede or deletion?

The production consequences are direct. Incorrect identity can cross tenant boundaries. Blind retry can
repeat expensive parsing. Overwriting versions destroys auditability. Accepting a stale candidate can move an
active pointer backwards. Deleting quarantined evidence prevents incident investigation. Day95 prevents these
failures before Day96 adds chunk identity and before Day99 introduces a vector index.

## 4. Roadmap Position

```text
Day49 upload session + artifact verification
        |
Day50 idempotency + transactional outbox
        |
Day64 candidate extraction + artifact evidence
        |
Day82 durable checkpoint/recovery
        |
Day86 untrusted-content quarantine
        |
Day94 proposal → authority → dispatch → candidate → Committer
        |
        v
Day95 untrusted source → validated immutable document truth
        |
        v
Day96 active parsed artifact → chunking experiments
        |
Day97 tenant/ACL/provenance → Day98 embeddings → Day99 index
```

Day95 reuses Day94's identity, candidate, Committer and reconciliation boundaries instead of creating a
second retry or operation model. Its new responsibility is document/source/version lifecycle. Day96 depends
on this lesson because chunking an uncommitted candidate would give every later RAG stage an unstable input.

## 5. Lesson Map

```text
identity vocabulary
→ untrusted source admission
→ immutable source reference
→ document/version/operation registration
→ parser preflight and dispatch claim
→ Adapter-owned candidate
→ manifest/correlation/output validation
→ sole Committer activation
→ duplicate and re-ingestion lifecycle
→ timeout/recovery/safe retry
→ quarantine/tombstone/evidence
→ exact Day96 eligibility
```

## 6. Core Mental Model

```text
Filename       = untrusted label
SourceArtifact = verified reference to received bytes
Parser result  = candidate
ParsedArtifact = validated immutable output
Active version = Committer-published durable fact
```

The full factory line is:

```text
untrusted source
→ verified source artifact
→ parser candidate
→ validated parsed artifact
→ ACTIVE immutable document version
→ Day96-eligible input
```

The shortest rule to remember is:

> A source artifact proves what bytes were received; an active version proves what validated result the
> application currently publishes.

## 7. Main Concepts

### Concept 1: Stable document identity and immutable versions

#### Tech Lead Question

Can `report-42.pdf` be the document identity, and can a changed upload overwrite `report-42-v2`?

#### Student Thinking

The learner correctly challenged filename identity: filenames are mutable and attacker-controlled. The
learner then separated the logical document pointer from immutable versions and concluded that changed content
must create a new `document_version_id`.

#### Student Answer

“filename 可篡改并不证明稳定的文档身份，`document_id` 是稳定的对象指针；changed content 需要
re-ingestion，已经上传的 version 不能覆盖。”

#### Tech Lead Review

`tenant_id + document_id` identifies one logical document. `document_version_id` identifies one immutable
version definition. Lifecycle state is mutable, but the version's source and parse-contract binding are not.
`Document.active_version_pointer` belongs to the logical document head, not to a version.

Exact duplicate and changed content are different outcomes:

```text
same operation + same complete source fingerprint → EXACT_DUPLICATE
same operation + different binding              → IDENTITY_CONFLICT
same document + changed bytes/contract           → new immutable version
```

#### Engineering Thinking

Immutable versions preserve rollback, provenance and reproducibility. The cost is more retained metadata and
artifacts. That cost is intentional: overwriting is cheaper until an incident requires the old source,
manifest or parser version.

#### Production Example

`tenant-a/report-42-v2` remains active while `report-42-v3` parses. If v3 fails, v2 stays active. If v3
succeeds, the Committer marks v2 `SUPERSEDED` and moves the pointer to v3 in one guarded transaction.

#### Framework Connection

An object-storage key locates bytes; it does not become the application document identity. A database row
owns the logical identity and lifecycle, while Object Storage owns immutable bytes.

#### Exercise

Classify these as stable, immutable-per-version, fresh-per-attempt or mutable concurrency facts:
`document_id`, `document_version_id`, `operation_id`, `parser_request_id`, `state`, `fence`.

### Concept 2: Source admission and content hash limits

#### Tech Lead Question

If extension, MIME and SHA-256 all look correct, is the upload now validated knowledge?

#### Student Thinking

The learner initially described content hash as proving “byte size unchanged.” The correction separated byte
equality from size, ownership, authorization, safety and semantic correctness.

#### Student Answer

“真实文件签名；不匹配应该 rejected，并保留 source artifact 和错误证据。”

#### Tech Lead Review

Source admission checks safe filename/path rules, non-empty size, resource budgets, expected checksum,
detected content signature and supported media contract. Extension and request Content-Type remain hints.
A hash compared with trusted expected evidence supports byte-integrity checks; it does not prove tenant
ownership, authorization, origin, meaning or safety.

Encrypted PDF, ZIP-disguised-as-PDF, malformed text and oversized input fail closed. The controlled classroom
parser supports text, Markdown and HTML; PDF is not silently passed to the text parser.

#### Engineering Thinking

Store bytes first, then persist the exact returned object key/version and observed evidence. Database failure
after object success can leave an orphan object, so production needs retention-aware reconciliation rather
than pretending PostgreSQL and Object Storage share one transaction.

#### Production Example

An attacker uploads `report.pdf` containing ZIP bytes and declares `application/pdf`. Filename and request
MIME agree, but signature detection rejects the source before parser or model access.

#### Framework Connection

FastAPI may receive multipart metadata, but the request body does not grant path, tenant or content-type
authority. Object Storage should use application-generated keys, versioning and conditional operations.

#### Exercise

Explain why two tenants uploading identical bytes cannot share one application artifact merely because the
SHA-256 values match.

### Concept 3: Parser candidate, validation and the sole Committer

#### Tech Lead Question

Why can a deterministic parser result not directly become the active document version?

#### Student Thinking

The learner identified correlation, manifest, structural, output and application-binding checks, then
corrected the language from “Committer is the executor” to “Committer is the durable transition authority.”

#### Student Answer

“parser result is only a candidate because it has not yet passed correlation, manifest, structural, output
and application-binding validation.”

#### Tech Lead Review

The Adapter is the only boundary that sees parser-private output. It returns an application-owned
`ParsedDocumentCandidate` plus a manifest binding tenant, document, version, source checksum, parser
name/version/contract, operation, idempotency identity, attempt/request/generation, output checksum and counts.

Successful validation creates a proposal, not a fact. The Committer compares document/version/operation
state, version and fence, then atomically:

1. saves the immutable parsed artifact;
2. activates the new version;
3. supersedes the previous active version;
4. moves the active pointer;
5. completes the ingestion operation;
6. records an outbox intent.

Only after that transaction may the application construct a verified ingestion observation.

#### Engineering Thinking

Candidate-only components can be replaced or retried without granting them database authority. The trade-off
is more DTOs and validation code, but negative-path call counts become explicit and reviewable.

#### Production Example

A late v2 parser response arrives after a newer attempt or fence advanced. Correlation or the Committer guard
rejects it; the result can remain `STALE_RESULT` evidence but cannot move the active pointer.

#### Framework Connection

A future PDF library, OCR service or RAG framework stays behind the Parser Adapter. Application contracts do
not change merely because a library renames fields or returns a different private object.

#### Exercise

Draw the authority boundary around the Parser Adapter, validator and Committer. Mark which component may call
the parser and which component may write durable lifecycle state.

### Concept 4: Unknown outcome, reconciliation and safe retry

#### Tech Lead Question

After `PARSE_DISPATCH_STARTED`, the worker crashes and the authoritative registry returns `NOT_FOUND`. Can a
new worker rerun the parser immediately?

#### Student Thinking

The learner rejected immediate replay: `NOT_FOUND` may reflect eventual consistency. The learner preserved
operation identity, kept the state pending and assigned durable lifecycle changes to the Committer.

#### Student Answer

“不能证明 parser 没有执行。operation 应保持 `PENDING_RECONCILIATION`；可以有界重查，最终仍查
不到时 operator alert。”

#### Tech Lead Review

The parser handoff occurs only after an atomic `PARSE_DISPATCH_STARTED` claim. No trusted response after that
point means possible execution. The Committer records `PENDING_RECONCILIATION`; the Recovery Coordinator
queries authority and never calls the parser.

```text
SUCCEEDED    → bind candidate → validate → Committer
FAILED       → Committer persists authoritative failure
NOT_EXECUTED → Committer persists fact → independent retry policy
NOT_FOUND    → remain pending → bounded re-query
UNKNOWN      → remain pending → bounded re-query/operator alert
```

Safe retry preserves operation, idempotency, tenant, document, version and source identity. It creates a
fresh attempt number and parser request ID, uses the current parser generation, reruns current preflight and
persists a new dispatch marker before handoff. Backoff and jitter control load; they do not create retry
safety.

#### Engineering Thinking

Recovery answers “what happened?” Retry policy answers “may another attempt run?” Committer answers “which
lifecycle fact may become durable?” Keeping these questions separate prevents an eventually consistent read
from causing duplicate work.

#### Production Example

The independent child parser finishes canonicalization but hangs before returning stdout. The parent times
out, records pending reconciliation and reports zero trusted parser-result calls. It does not infer failure.

#### Framework Connection

The bounded retry policy reuses Day93 evidence and deadline rules. The orchestration layer routes its typed
decision but does not invent `PROVEN_NOT_EXECUTED`.

#### Exercise

For each status—`SUCCEEDED`, `FAILED`, `NOT_EXECUTED`, `NOT_FOUND`, `UNKNOWN`—write the next component and
prove whether parser calls, validation calls and Committer calls should be zero or one.

### Concept 5: Quarantine, tombstone and the Day96 gate

#### Tech Lead Question

Should unsafe input be deleted immediately, and is quarantine the same as tombstone?

#### Student Thinking

The learner first grouped quarantine and tombstone together, then corrected the model: quarantine is a safety
isolation state; tombstone is a lifecycle unavailability fact. Both retain evidence.

#### Student Answer

“Atomically mark the unsafe version and operation `QUARANTINED`, block parser/model/chunking, retain source,
checksum, bindings, rejection reason and audit evidence.”

#### Tech Lead Review

`QUARANTINED` blocks unsafe or invalid input from parsing, model context, activation and Day96. `TOMBSTONED`
states that a document/version is deleted, withdrawn or unavailable. Neither means “erase evidence now.” A
future purge must separately confirm retention expiry and absence of durable published references.

Day96 eligibility is one exact predicate:

```text
Document.state == ACTIVE
AND Document.active_version_pointer == target version
AND DocumentVersion.state == ACTIVE
AND parsed_artifact_id exists
AND IngestionOperation.state == COMPLETED
```

#### Engineering Thinking

Keeping lifecycle facts separate from physical deletion preserves auditability and avoids races with
downstream references. The cost is a later retention/purge workflow, intentionally deferred beyond Day95.

#### Production Example

An encrypted source is quarantined while v2 remains active. A user later deletes the logical document; a
tombstone removes the active pointer but retains the source and parsed evidence until retention policy allows
physical purge.

#### Framework Connection

Day96 receives only the parsed artifact selected by the full predicate. A vector database is not consulted or
mutated in Day95; index deletion belongs to Day104.

#### Exercise

Explain why `SUPERSEDED`, `QUARANTINED` and `TOMBSTONED` all fail Day96 eligibility for different reasons.

## 8. Common Misconceptions

### Filename identity

❌ The filename or object key identifies the logical document.

✅ The application establishes tenant-bound `document_id`; filename is a label and object key is a storage
locator.

### Content hash

❌ Equal hash proves authorization, safety and semantic correctness.

✅ A trusted hash comparison supports byte-equality/integrity evidence under one algorithm only.

### Parser success

❌ A deterministic parser can publish its result directly.

✅ Determinism does not replace correlation, manifest, output, application and Committer checks.

### `NOT_FOUND`

❌ Registry `NOT_FOUND` proves the parser did not execute.

✅ Under eventual consistency it may be a temporarily incomplete view; remain pending.

### Backoff

❌ Backoff makes any retry safe.

✅ Backoff manages traffic. Only trusted non-execution evidence creates retry eligibility.

### Re-ingestion and retry

❌ Both preserve every identity.

✅ Retry preserves the operation/version/source and rotates attempt identity. Re-ingestion preserves the
logical document but normally creates a new version/source/operation.

### Quarantine and tombstone

❌ Both mean “delete the file.”

✅ Quarantine isolates unsafe input; tombstone publishes unavailability. Physical purge is separate.

## 9. Engineering Trade-offs

### In-memory lifecycle model vs production database

The classroom model makes conditional transitions deterministic and reviewable. It does not prove database
isolation, crash durability or multi-node fencing. Production should use a transactional store with guarded
updates and an outbox.

### In-process parser vs independent parser service

In-process parsing is simpler and faster. An independent process gives a meaningful timeout and resource
boundary but adds serialization, process supervision and reconciliation. Day95 tests both local Adapter logic
and a real child-process path; it does not claim a production parser deployment.

### Exact duplicate reuse vs always create a version

Reuse reduces work when the complete tenant/document/source/contract fingerprint matches. Always creating a
version simplifies intake but creates noise. Neither policy may deduplicate across tenant authority or let a
hash replace identity checks.

### Retain evidence vs immediate deletion

Retention improves incident response and lineage, but increases storage and privacy obligations. Physical
purge should be explicit, reference-aware and policy-driven rather than an implicit effect of quarantine.

## 10. Hands-on Exercises

### Exercise 1: Identity classification

Question: Classify every field in the first production incident.

Think First: Is it logical identity, immutable version identity, attempt identity or concurrency state?

Starter Artifact: `operation_id`, `document_version_id`, `parser_request_id`, `fence`, `filename`.

Expected Output: A table that keeps filename outside authority and separates stable operation fields from
fresh attempt fields.

Explanation: Most unsafe retries begin by rotating the wrong identity or trusting presentation metadata.

Follow-up Question: Which identities change during re-ingestion rather than retry?

### Exercise 2: Unknown-outcome call counts

Question: A child parser times out after possible parsing. Specify parser transport, validation and Committer
call counts.

Think First: What evidence exists after dispatch and before a trusted response?

Starter Artifact: The `PENDING_RECONCILIATION` state transition.

Expected Output: One transport handoff, zero trusted candidate validation, one pending-state Committer call,
and no parser replay.

Explanation: Explicit counts make authority leaks testable.

Follow-up Question: What changes after authoritative `SUCCEEDED`?

### Exercise 3: Design the production replacement

Question: Replace the in-memory store and local child parser without weakening ordering.

Think First: Where are transactions possible, and where are they not?

Starter Artifact: Object Storage + PostgreSQL + parser service + authoritative registry.

Expected Output: Bytes first, immutable object result, database registration/outbox, preflight, guarded claim,
remote parser, candidate validation, Committer and reconciliation.

Explanation: “Use PostgreSQL” is insufficient unless state/version/fence and object/database orphan handling
are explicit.

Follow-up Question: Which failure drills are required before production readiness?

## 11. Relevant Framework Connections

### FastAPI

FastAPI can authenticate the upload/reference request and enforce body limits, but request fields remain
untrusted. The API should return operation/document identities, not expose internal object paths as authority.

### Object Storage

Object Storage holds immutable source bytes and may later hold parsed artifacts. Versioning, checksums,
conditional operations, retention and consistency require provider-specific runtime evidence.

### PostgreSQL and transactional outbox

A production Committer can use conditional `UPDATE ... WHERE state/version/fence ... RETURNING` inside one
transaction and write an outbox intent with the lifecycle facts. PostgreSQL cannot atomically include a prior
Object Storage write, so orphan reconciliation remains necessary.

### MCP and Agent Runtime

Day94's proposal/authority/candidate/Committer and unknown-outcome rules are reused. Parser services and RAG
frameworks do not gain authorization or durable lifecycle authority merely because an Agent calls them.

## 12. AI Backend Connections

Day95 creates the stable input for Production RAG. Day96 can compare chunking strategies only if every chunk
references one immutable parsed artifact and document version. Day97 can add ACL/provenance only if tenant and
source lineage already exist. Embedding and vector-index versions cannot repair ambiguous source identity
later.

This ordering also controls AI security and cost:

- quarantined content never enters model context;
- duplicate intake can avoid repeated parsing;
- stale output cannot trigger chunking/embedding work;
- provenance survives supersede and tombstone;
- observability may explain a failure but cannot publish knowledge.

## 13. English Interview

### Key vocabulary

`source artifact`, `logical document`, `immutable version`, `parsed candidate`, `parse manifest`, `lineage`,
`provenance`, `supersede`, `quarantine`, `tombstone`, `reconciliation`, `durable transition`.

### Useful expressions

- “A source artifact proves what bytes were received; it is not validated knowledge.”
- “The parser returns a candidate, while the Committer establishes the durable lifecycle fact.”
- “`NOT_FOUND` is not proof of non-execution under eventual consistency.”
- “Re-ingestion preserves logical document identity and creates a new immutable version.”

### Beginner question

What is the difference between a source artifact and an active document version?

**Strong answer:** A source artifact is an admitted immutable reference to received bytes. An active version
is a Committer-published fact whose parsed artifact passed correlation, manifest, structural, output and
application validation.

### Intermediate question

How should the system handle parser timeout after possible output creation?

**Strong answer:** Persist pending reconciliation, query an authoritative registry without replaying the
parser, keep `NOT_FOUND/UNKNOWN` pending, validate resolved success, and retry only after the Committer records
authoritative non-execution.

### Senior question

Design a restart-safe RAG ingestion pipeline.

**Strong answer:** Establish tenant-bound document/version/source/operation identity, admit immutable bytes,
run current preflight, persist the dispatch marker before handoff, keep parser types in an Adapter, validate
the candidate, activate only through a guarded Committer, and recover from durable facts through read-only
authority queries. Preserve lineage and rotate only attempt identity on a safe retry.

### Common weak answer

“Upload the PDF, split it, embed it and retry parsing with exponential backoff on error.”

This omits source safety, identity, immutable versions, dispatch uncertainty, candidate validation, Committer
authority, reconciliation, tenant boundaries and evidence levels.

### Classroom result

`PASS_WITH_LANGUAGE_CORRECTIONS`. The learner reached the senior architecture model. Required corrections
included retry versus re-ingestion identity, hash limits, reconciliation versus parser retry, quarantine
versus tombstone, and the complete Day96 eligibility predicate.

## 14. Mental Model Summary

```text
filename            = untrusted presentation metadata
object key           = storage locator
source artifact      = admitted immutable bytes reference
document             = stable tenant-bound logical identity
document version     = immutable source/contract definition
parser attempt       = attempt number + request ID + generation
parsed candidate     = untrusted application DTO
parsed artifact      = validated immutable output
active pointer       = current published version selection
Committer            = sole durable lifecycle authority
reconciliation       = observe existing outcome, never replay
retry                = only after committed non-execution
```

## 15. Today's Takeaway

The most important mental model is that ingestion converts untrusted bytes into document truth through a
sequence of narrow evidence and authority boundaries. The highest production risk is accepting or replaying
work when identity or execution status is ambiguous. The central trade-off is additional durable metadata and
validation complexity in exchange for recoverability, auditability and safe evolution.

For AI Backend work, Day95 means chunking, embedding and vector indexing must consume only a validated active
version. For interviews, remember: parser success is a candidate; only a guarded Committer can publish the
active document fact.

## 16. Before Next Lesson Checklist

- [ ] Can I distinguish filename, object key, source artifact, document and document version?
- [ ] Can I explain why a content hash does not prove authorization or meaning?
- [ ] Can I identify stable operation fields, fresh attempt fields and mutable concurrency facts?
- [ ] Can I explain why dispatch claim precedes parser handoff?
- [ ] Can I list every candidate-validation stage?
- [ ] Can I explain what the sole Committer atomically changes?
- [ ] Can I distinguish duplicate, conflict, re-ingestion and supersede?
- [ ] Can I distinguish quarantine, tombstone and physical purge?
- [ ] Can I explain why `NOT_FOUND` remains pending?
- [ ] Can I explain why reconciliation is not parser retry?
- [ ] Can I state the exact Day96 eligibility predicate?
- [ ] Can I name the missing production evidence?
- [ ] Can I answer the restart-safe ingestion question in English?
