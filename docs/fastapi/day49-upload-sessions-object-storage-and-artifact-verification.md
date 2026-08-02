# Day49 — Upload Sessions, Object Storage and Artifact Verification

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day48 — Alembic and Safe AI Backend Schema Evolution
Previous Lesson: Day48 — Alembic and Safe AI Backend Schema Evolution
Next Lesson: Day50 — Idempotent Job Acceptance and Atomic Job/Outbox Intent
Engineering Artifact: projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md
  + runnable day49_upload_verification.py + test_day49_upload_verification.py (fake in-memory adapter; 17 passed)
```

Main engineering artifact: a provider-neutral upload-verification control-flow model with a fake in-memory Object
Storage adapter, plus the [design/runbook](../../projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Explain** why "Object Storage accepted the write" is a storage-layer fact, not a verified business fact.
- **Design** a server-owned deterministic object identity (bucket + key + immutable version) and defend why the
  client must not choose the internal key.
- **Compare** a presigned URL (a scoped bearer credential) with durable Artifact identity, and explain why a
  presigned URL is not naturally one-time.
- **Implement** expected-vs-observed verification that never rewrites the frozen expectation and never treats an
  ETag as a SHA-256.
- **Diagnose** the completion-vs-cleanup race and resolve it with a short guarded DB transition plus idempotent
  external cleanup — never a DB lock held across Object Storage I/O.
- **Apply** idempotent finalization for a Document and coherent output-ordering for a ResultArtifact.
- **Recover** unknown external outcomes (timed-out multipart Complete, crash before DB completion) from evidence,
  without re-calling a paid Provider.
- **Connect** the boundary to FastAPI, PostgreSQL/SQLAlchemy, Alembic, and AI Job provenance.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

A multi-tenant AI research platform receives a 2 GB research file that will feed an expensive AI Job. If FastAPI
proxies the 2 GB byte stream, one request ties up a worker for minutes, blows memory, and couples the API's uptime
to the upload. So the client uploads **directly** to Object Storage with a presigned credential, and FastAPI only
creates and later verifies an Upload Session.

The trap is treating the storage `200 OK` as truth. A write being accepted does **not** prove the object is the
expected key/version, owned by the expected tenant/session, complete, immutable, safe, or suitable for an AI Job.
If you create a `Document` on storage success alone, you can feed corrupted, overwritten, cross-tenant, or
malicious bytes into a paid AI pipeline, publish results derived from the wrong input, and have no deterministic
way to recover after a crash. Production risk is data corruption, security exposure, wasted Provider spend, and
false "succeeded" facts. This lesson makes external bytes become **deterministic, verified, recoverable** database
references.

---

## 4. Roadmap Position

```text
Day48 Safe schema evolution (Alembic; external side effects outside PG rollback; reconcile unknowns)
        |
        v
Day49 Verified external-object boundary  ->  durable Document / ResultArtifact references   <-- you are here
        |
        v
Day50 Idempotent Job acceptance + atomic Job/Outbox intent (against already-verified Documents)
        |
        v
Day51 Authentication  ->  Day52 Authorization + tenant isolation + quota  ->  Day55 Celery worker transport
```

### Knowledge Continuity

```text
Previous Knowledge
  Day47 short Unit of Work + guarded state transition
  Day48 external side effects live outside PostgreSQL rollback; reconcile unknowns from evidence
  Day31/Day46 schema: UploadSession 1 -> 0..1 Document via UNIQUE(documents.upload_session_id),
                      same-tenant provenance via the composite FK (tenant_id, upload_session_id)
        |
        v
Current Lesson Concept
  Upload success != verified; server-owned identity; expected-vs-observed verification;
  idempotent finalization; completion/cleanup concurrency; unknown-outcome reconciliation
        |
        v
Future Production Usage
  Day50 accepts Jobs only against verified Documents; Day52 authorizes access;
  browser/RAG workflows consume deterministic verified Artifact references
```

Day48 did **not** implement upload sessions, Object Storage runtime, Artifact verification, or a real
PostgreSQL/Object Storage integration. Day49 reuses its three boundaries and adds the verified external-object
layer. It does not pre-implement Day50 Outbox, Day51 JWT, Day52 authorization, Day55 Celery, or a real Provider.

---

## 5. Lesson Map

```text
Storage success vs verified business fact
  -> Server-owned deterministic identity (bucket / key / version)
  -> Presigned credential (scoped, replayable, not identity)
  -> Expected vs observed verification (never rewrite expectation; ETag != SHA-256)
  -> Upload Session vs Document (temporary protocol vs durable verified asset)
  -> Content/security gates (separate from byte integrity; fail-closed)
  -> Idempotent finalization UoW (Document)
  -> Completion vs cleanup concurrency + three expiry lifecycles
  -> Multipart for 2 GB + unknown-completion recovery
  -> Output ResultArtifact ordering + crash recovery (no Provider re-call)
  -> Tenant-aware relational integrity (UNIQUE vs composite FK)
  -> Evidence levels
```

---

## 6. Core Mental Model

```text
Upload success  = storage-layer fact
Verified        = backend business fact supported by evidence

Upload Session  = durable temporary workflow state for ONE server-owned upload identity
Presigned URL   = short-lived least-privilege BEARER credential for an exact operation (never identity)
Bucket + key + immutable version = deterministic identity of external bytes
Document        = durable verified reusable INPUT reference   (not the bytes)
ResultArtifact  = durable verified OUTPUT reference for a JobAttempt (not the bytes)

Verification = frozen expected contract == trusted observed object evidence
             + content / parser / security / business-policy gates

Safe finalization = external verification OUTSIDE a DB tx
                  -> short PostgreSQL UoW creates the reference + flips state atomically

Recovery = inspect external evidence -> re-read PostgreSQL truth
         -> idempotent guarded transition -> reconciliation, never blind side-effect retry
```

The whole lesson is one sentence: **storage accepting bytes is not the same as your backend trusting them.**

---

## 7. Main Concepts

### Concept 1: Storage success is not a verified business fact

**Tech Lead Question:** Object Storage returns `200` for the 2 GB upload. Can you immediately mark the session
verified and create the Document?

**Student Thinking:** The upload "worked", so maybe the object is ready — but something still has to check it.

**Student Answer:** "不能，因为需要对上传的内容进行校验"

**Tech Lead Review:** Correct instinct. A `200` proves the storage layer accepted a write. It does not prove the
object is the expected key/version, complete, immutable, tenant-owned, safe, or semantically valid. `Upload
success = storage-layer fact; Verified = backend business fact supported by evidence.` You verify before you
create any durable business truth.

**Engineering Thinking:** Trust boundaries must be explicit. The storage system and your business invariants are
different authorities; conflating them lets unverified bytes become business facts.

**Production Example:** A retried client PUT overwrites the object after your app "saw" a good upload; without a
pinned version + verification you would attach a Document to bytes you never checked.

**Framework Connection:** FastAPI returns a credential and later runs verification; it never proxies or trusts the
raw upload result.

---

### Concept 2: The server owns deterministic object identity

**Tech Lead Question:** Who decides the object key — the client (from the filename) or the server?

**Student Answer:** "应在创建 Upload Session 时由后端确定"

**Tech Lead Review:** Right. The server chooses `bucket + key` when creating the session; the client chooses bytes
and declares metadata. The original filename is untrusted and must never control the internal path. Completion
loads the **persisted** key and rejects a different client-supplied key. Example shape (do not hard-code if repo
conventions differ): `uploads/{tenant_id}/{upload_session_id}/source`.

**Engineering Thinking:** Deterministic, server-owned identity is what makes verification and recovery possible: a
crash can always re-derive exactly which object to inspect.

**Production Example:** Two tenants upload `report.pdf`; server-owned keys keep them isolated and collision-free
regardless of filename.

**Framework Connection:** `derive_object_key(tenant_id, upload_session_id)` in the artifact; `finalize_upload`
returns `REJECTED_KEY` if the client key differs from the persisted one.

---

### Concept 3: Bucket, key, version — and why a presigned URL is not one-time

**Tech Lead Question:** A presigned URL is still valid after the first upload. Is the stored object trustworthy,
and how do you stop a silent overwrite?

**Student Thinking:** The student saw the overwrite risk and reached for "one URL = one file".

**Student Answer:** "不可信，可能已经被覆盖，应该同一个presigned URL只能上传一个文件" — and, on the underlying
storage terms: "不知道，还有个问题bucket是什么"

**Tech Lead Review:** The overwrite instinct is correct, but a presigned URL is normally a **replayable bearer
credential** valid for a scoped operation until expiry; a one-time completion endpoint does not revoke direct
storage writes. Enforce immutability with a **per-session unique never-reused key** plus **create-only**
conditional writes or **versioning + a persisted version ID**. And the vocabulary: **Bucket** = top-level
namespace/policy/config container (not a folder); **object key** = identity within a bucket (`/` is convention,
not automatically a security boundary); **version** pins the exact immutable bytes. A reference is conceptually
`bucket + key + version` + verification evidence. A presigned URL is a credential, never the durable identity.

**Engineering Thinking:** You cannot make an external system one-time by wishing it; you make identity immutable
and verify the pinned version.

**Production Example:** Short expiry lowers replay risk but a leaked URL can still overwrite until it expires —
create-only or versioning is the real guard.

**Framework Connection:** `ObjectReference(bucket, key, version)`; the fake adapter assigns a new version per PUT
so an overwrite is a distinct immutable version.

---

### Concept 4: Expected vs observed verification

**Tech Lead Question:** The completion request sends a checksum, and Object Storage also reports one. Which do you
trust, and what do you compare?

**Student Answer (checksum trust):** "相信Object Storage metadata"

**Tech Lead Review:** Trusting storage inspection over the untrusted completion request is the right direction —
but the durable rule is: freeze the **expected** size/checksum/content-type in the session **before** upload, then
compare it against **trusted observed** evidence. **Never overwrite the expectation** to make a mismatch pass. And
an ordinary **ETag is not a SHA-256** (multipart/encryption change it), so do not accept an ETag as the full-object
hash. FastAPI does not download 2 GB just to hash it if the provider can expose a trustworthy full-object checksum;
otherwise an isolated async verifier streams it. Mismatch -> failed/quarantine, no Document, no Job.

**Engineering Thinking:** Verification is a comparison against a frozen contract, not a re-derivation of the
contract from whatever the object happens to be.

**Production Example:** A truncated multipart object reports a smaller size; the frozen expected size catches it.

**Framework Connection:** `verify_object(expected, observed)` returns a new result and never mutates the frozen
`ExpectedContract`; a `None` full-object SHA-256 is a hard mismatch.

---

### Concept 5: Upload Session vs Document (and why Document exists)

**Tech Lead Question:** Why not just keep everything on the Upload Session? Why a separate Document?

**Student Answer:** "document保存其他的信息"

**Tech Lead Review:** Close, but sharpen it. **Upload Session** = temporary upload protocol/lifecycle (initiated,
uploading, failed, expired). **Document** = durable **verified** input business asset that may be reused by many
Jobs. Document is not the large bytes; it is a PostgreSQL fact/reference with provenance and evidence. Jobs must
not reference temporary, failed, or expired sessions directly. The relation is `UploadSession 1 -> 0..1 Document`
via `UNIQUE(documents.upload_session_id)`.

**Engineering Thinking:** Separating transient protocol state from durable verified assets keeps reuse, audit, and
lifecycle clean.

**Framework Connection:** `DocumentRow` vs `UploadSessionRow` in the artifact; a Document is created only inside
the guarded finalization UoW.

---

### Concept 6: DB-commit failure after upload — idempotent finalization

**Tech Lead Question:** The object uploaded fine, but the PostgreSQL commit that creates the Document fails. Do
you re-upload?

**Student Answer:** "只更新数据库事务，不重新上传，需要幂等键"

**Tech Lead Review:** Right not to re-upload — the object is deterministic and immutable, so retry re-inspects the
same object and retries only the short DB finalization. One refinement: Day49's natural stable identity is
`upload_session_id` + a guarded transition + `UNIQUE(documents.upload_session_id)`. Day50's tenant-scoped client
idempotency key solves a different problem (Job acceptance); don't conflate them.

**Engineering Thinking:** Idempotency comes from deterministic identity + a guarded transition, not from
re-doing expensive external work.

**Framework Connection:** `finalize_upload` short-circuits to `ALREADY_VERIFIED` and returns the existing
Document; a lost race hitting `UNIQUE` also collapses to `ALREADY_VERIFIED`.

---

### Concept 7: Completion vs cleanup concurrency

**Tech Lead Question:** A completion request and a cleanup worker act on the same session at once. How do you keep
them from corrupting each other?

**Student Answer:** "应该有一个类似锁的机制" — and on a late write after expiry: "不知道"

**Tech Lead Review:** Serialize them on the **database** state with `SELECT ... FOR UPDATE` or a guarded UPDATE. A
DB lock cannot make Object Storage atomic, so **never hold a DB row lock across slow storage I/O**. If completion
commits `verified` + Document first, cleanup's eligible-state predicate affects zero rows and must not delete the
object. If cleanup commits `expired` first, completion's final guarded check fails and creates no Document. Cleanup
commits the durable decision first, then deletes the exact unverified object/version outside the DB tx; a failed
delete leaves a recoverable orphan, not a dangling verified fact.

**Engineering Thinking:** Use the database as the serialization point for the decision, and reconciliation for the
external effect.

**Framework Connection:** `classify_cleanup` returns `KEEP_VERIFIED`/`KEEP_HAS_DOCUMENT` for a verified/documented
session and `KEEP_TOO_EARLY` before the timing gate.

---

### Concept 8: Three expiry lifecycles and the cleanup timing gate

**Tech Lead Question:** A URL expires at 12:00. Max clock skew is 2 minutes and you want a 1-minute safety buffer.
What is the earliest safe delete time?

**Student Answer:** "12:03"

**Tech Lead Review:** Correct. `cleanup_not_before = credential_expiry + clock_skew + safety_buffer = 12:00 + 2m +
1m = 12:03`. Keep the three lifecycles distinct: **session expiry** (backend stops accepting completion),
**credential expiry** (storage stops honoring the signed credential), **cleanup eligibility** (credential expiry +
skew + buffer). Session expiry must not precede credential expiry.

**Engineering Thinking:** Distributed clocks and in-flight credentials mean "expired" is a window, not an instant;
buffers prevent deleting an object a late-but-valid write is still producing.

**Framework Connection:** `cleanup_not_before(credential_expires_at, max_clock_skew, safety_buffer)`.

---

### Concept 9: Content/security scanning and scanner outage

**Tech Lead Question:** Checksum matches. Is the document safe to feed an AI Job? And if the malware scanner is
down, do you fail open or fail closed?

**Student Answers:** "还需要进行安全扫描" and "让Upload Session 等待，因为可能之后会造成更大的破坏"

**Tech Lead Review:** Both right. Identity/integrity is separate from safety and semantic validity. Layered gates:
storage identity/integrity; real media-type detection from bytes; parser/structure + bounded-resource checks;
malware/decompression-bomb checks in isolation; business/tenant policy. On a **mandatory** gate, a scanner outage
is **fail-closed**: keep waiting with bounded backoff and create no Document; permanent bad content is
failed/quarantined, not retried forever. The 2 GB scan must not run inside a request transaction. Note: passing a
malware scan does not make the document's *content* trustworthy against semantic errors or prompt injection.

**Framework Connection:** `finalize_upload` returns `SCAN_RETRY_LATER` (session stays `uploading`) on
`ScannerUnavailable`, and `SCAN_FAILED` (session `failed`) on an unsafe verdict.

---

### Concept 10: Multipart upload and unknown Complete

**Tech Lead Question:** 2 GB over ~45 minutes with short-lived credentials — single PUT or multipart? And if
`CompleteMultipartUpload` times out, do you restart the upload?

**Student Answers:** "采用 multipart upload"; parts vs object: "不能因为还没有组装"; unknown Complete: "先做别的事";
first recovery evidence: "checksum"

**Tech Lead Review:** Multipart is correct: `upload_id`, per-part short-lived credentials, bounded
numbers/sizes/checksums, selective retry, controlled final assembly. **Part success = transport progress, not a
final object and not a Document** — right again. A timed-out Complete is an **unknown external outcome**: inspect
the deterministic final object first; if it exists and matches, treat Complete as succeeded; if absent, inspect the
same `upload_id`/parts and recover the same operation — **do not blindly start a new upload**. And recovery
evidence is a **bound tuple** (bucket/key/version/existence/size/full checksum), not a checksum string in
isolation.

**Framework Connection:** `classify_multipart_completion` -> `COMPLETE_SUCCEEDED` / `FINAL_OBJECT_MISMATCH` /
`RECOVER_FROM_PARTS` / `PARTS_NOT_ASSEMBLED`.

---

### Concept 11: Output ResultArtifact ordering and crash recovery

**Tech Lead Question:** Do you mark the Job succeeded first, or write+verify the result object first?

**Student Answers:** "选B，因为先标记，如果没有上传结果则是一个错误的数据库事实" (i.e. marking first is wrong); crash
recovery: "还是根据确定性 Artifact 引用进行恢复"

**Tech Lead Review:** Correct: never mark a Job succeeded before its result reference can be committed coherently,
or you publish a false fact when the result is absent. Ordering: upload output bytes -> verify immutable evidence
-> short UoW inserts ResultArtifact + JobEvent and guardedly marks the Job succeeded. On a crash after the verified
output upload but before DB completion, **do not call the paid Provider again**: re-read Job/Attempt/Event, inspect
the deterministic object, then do an idempotent guarded completion; if evidence is missing/inconsistent, preserve
the unknown/recovery state.

**Framework Connection:** `classify_result_recovery` -> `COMPLETE_IDEMPOTENT_NO_PROVIDER` / `PRESERVE_UNKNOWN` /
`ALREADY_COMPLETED`.

---

### Concept 12: Tenant-aware relational integrity

**Tech Lead Question:** `UNIQUE(upload_session_id)` — does that also guarantee the Document belongs to the same
tenant as its session?

**Student Answer:** "用unique"

**Tech Lead Review:** `UNIQUE` prevents duplicate Documents per session but does **not** prove same-tenant
provenance. The existing Day31 design carries that with a **composite FK** `(tenant_id, upload_session_id)
REFERENCES upload_sessions(...)` `ON DELETE RESTRICT`. Composite FK = persistent relationship integrity, not
request authorization (Day52 does authorization).

**Framework Connection:** `InMemoryStore.create_document` raises `DuplicateDocumentError` (UNIQUE) and
`ProvenanceError` (composite FK) — modeled, not real PostgreSQL FK proof.

---

### Concept 13: Evidence levels

**Tech Lead Question:** Do fake-adapter tests prove the real presigned/checksum/multipart semantics?

**Student Answer:** "不能，因为还需要实际的runtime"

**Tech Lead Review:** Exactly. Conceptual design, static checks, fake runtime, real PostgreSQL runtime, local
S3-compatible integration, target-cloud integration, and production validation are distinct claims. SQLAlchemy
metadata inspection proves declaration, not FK behavior; fake adapter tests prove control flow, not real storage
semantics.

**Integrated race (student synthesis):** "completion B根据artifact以及数据库事实判断进行短事务提交。cleanup worker
随后进行扫描，发现没有可清除的" — matches the intended outcome: B re-reads and returns the existing Document; cleanup's
guarded eligible-state UPDATE affects zero rows and does not delete the verified version.

---

## 8. Common Misconceptions

Presigned URL as a one-time primitive
❌ One upload session should accept one file, so a presigned URL is one-time.
✅ A presigned URL is normally replayable until expiry; the invariant is immutable verified object identity
   (unique never-reused key + create-only or pinned version).
Why beginners think this: "one session, one file" feels safe. How to remember: a bearer credential is not a
mutex — pin the version.

Bucket/object/version terminology
❌ A bucket is a filesystem directory and the key path is a security boundary.
✅ A bucket is a top-level namespace/policy/config container; the key is identity; the version pins bytes; `/` is
   convention, not automatically a boundary.

Trusting the observed checksum by replacing the expectation
❌ Set expected = observed so it always matches.
✅ Freeze expected before upload and compare; never overwrite the expectation.

Completion needs "an idempotency key"
❌ Add a client idempotency key to finalize the upload.
✅ Day49's stable identity is `upload_session_id` + guarded transition + `UNIQUE(upload_session_id)`; the client
   idempotency key is Day50's Job-acceptance concern.

Document as merely a richer upload record
❌ Document just stores extra upload fields.
✅ Upload Session is temporary protocol state; Document is a durable verified reusable input asset (a reference,
   not bytes).

Lock as a cross-system transaction
❌ A DB lock makes the Object Storage delete atomic with the DB decision.
✅ DB locks serialize the DB decision only; use a short DB tx then idempotent external cleanup + reconciliation,
   never a DB lock held over storage I/O.

UNIQUE for cross-tenant provenance
❌ `UNIQUE(upload_session_id)` proves the Document is same-tenant.
✅ UNIQUE prevents duplication; same-tenant provenance needs the composite FK.

Checksum alone for unknown multipart completion
❌ Compare a checksum string to decide if Complete succeeded.
✅ Inspect the bound tuple (bucket/key/version/existence/size/full checksum); if absent, inspect the original
   `upload_id`/parts.

ETag equals SHA-256
❌ Use the ETag as the content hash.
✅ ETag is provider-defined and differs for multipart/encryption; require a trustworthy full-object SHA-256.

"摇摆时间"
❌ Vague "wobble time".
✅ Bounded **clock skew** plus an explicit **cleanup safety buffer**.

---

## 9. Engineering Trade-offs

```text
FastAPI proxies bytes  vs  Direct-to-Object-Storage presigned upload
Proxy: simplest client; but ties API uptime/memory/worker time to a 2 GB transfer -> rejected for large files.
Direct: scalable, decoupled; but requires server-owned identity + explicit verification + cleanup.

Single PUT  vs  Multipart
Single: fewer moving parts; fails whole on one network blip; hard with short credentials over 45 minutes.
Multipart: resumable, selective retry, bounded parts; but needs abort/lifecycle for incomplete parts and
unknown-Complete recovery.

External-first (upload+verify, then DB)  vs  DB-first (mark, then upload)
External-first: worst case a recoverable orphan; recovery is deterministic. -> chosen.
DB-first: can publish a false "succeeded"/"verified" with no object behind it. -> rejected.

Fail-open  vs  Fail-closed on a mandatory scan gate
Fail-open: availability; but can admit malicious/invalid content. -> rejected for mandatory safety.
Fail-closed: safety; but blocks progress during a scanner outage (bounded backoff, no Document). -> chosen.

Keep session 'uploading' until all gates pass  vs  Add a 'verifying' status
Keep 'uploading': no schema/Alembic change, no CHECK edit, minimal. -> chosen for Day49.
Add 'verifying': better operational visibility; but a Day48-safe forward branch revision + wider blast radius.

Object Storage lifecycle rule cleanup  vs  Application-driven guarded cleanup
Lifecycle rule: cheap, automatic; but can delete objects you still need if scoped wrong -> never let it delete
verified Documents.
App-driven: precise, guarded by DB state; more code. Use both as defense in depth, scoped carefully.
```

A Tech Lead reviews: is identity server-owned? Is the expectation frozen and never rewritten? Is a DB lock ever
held across storage I/O? Can a false "succeeded" be published? Are unknown outcomes reconciled or blindly retried?

---

## 10. Hands-on Exercises

### Exercise 1: Does storage `200` permit verified status?

Question: Object Storage returns `200`. Mark verified?
Think First: what does `200` actually assert?
Expected Output: No — `200` is a storage-layer fact; verify key/version/size/checksum + security first.
Explanation: `Upload success != verified`.
Follow-up: name two things `200` does not prove.

### Exercise 2: Who owns `object_key`?

Expected Output: the server, at session creation; the filename is untrusted metadata.
Follow-up: what does `finalize_upload` do with a different client key? (`REJECTED_KEY`.)

### Exercise 3: Compute `cleanup_not_before`

Question: URL expires 12:00, max skew 2m, buffer 1m. Earliest delete?
Expected Output: **12:03**.
Follow-up: why not delete exactly at 12:00?

### Exercise 4: Resolve expected vs observed mismatch (design)

Question: observed size differs from expected. What happens, and what must you never do?
Expected Output: mark failed/quarantine, no Document; never overwrite the frozen expectation; never accept ETag as
SHA-256.
Follow-up: when may FastAPI stream the object to hash it?

### Exercise 5: Recover a timed-out multipart Complete (design judgment)

Question: `CompleteMultipartUpload` times out. Restart the upload?
Think First: what is the deterministic evidence?
Expected Output: inspect the final object first; matches -> succeeded; absent -> inspect `upload_id`/parts; never
blindly restart.
Follow-up: are uploaded parts a Document? (No.)

### Exercise 6: Integrated failure/rollback (reusable analysis)

Question: concurrent completion A/B, response lost after A commits, cleanup racing. What does B do, and cleanup?
Expected Output: B re-reads and returns the existing Document; cleanup's guarded eligible-state UPDATE affects zero
rows and does not delete the verified version.
Follow-up: why is no DB lock held across the storage delete?

---

## 11. Relevant Framework Connections

- **FastAPI** — creates Upload Sessions and returns scoped presigned credentials; it does **not** proxy 2 GB bytes
  or scan inside a request transaction. Verification/finalization are separate, short operations.
- **PostgreSQL / SQLAlchemy** — durable session/document/artifact facts; `UNIQUE(documents.upload_session_id)`;
  the composite tenant-aware FK; guarded transitions; short UoWs (Day47). Metadata inspection proves declaration,
  not real FK behavior.
- **Alembic** — any new state/columns/constraints follow Day48 safe **forward** evolution (branch + merge if
  needed); no revision-history rewrite; no destructive Contract auto-crossed. Day49 deliberately needs none.
- **Object Storage** — bucket/key/version, presigned credentials, metadata/full checksum, multipart, abort,
  versioning, lifecycle, inventory, and external-side-effect recovery. A presigned URL is a bearer credential,
  never Artifact identity.
- **Background scanner** — a conceptual verification workload; no Celery runtime is claimed (Day55).

---

## 12. AI Backend Connections

- Large research Documents are **verified external inputs** for AI Jobs; feeding unverified bytes wastes paid
  Provider spend and pollutes provenance.
- Paid Provider results become **verified ResultArtifacts**, published with the Job's terminal state coherently —
  never mark succeeded before the result reference commits.
- **Do not rerun a Provider** merely because a DB response or worker process was lost; inspect the deterministic
  object and reconcile.
- Malware safety does **not** make document content trustworthy against semantic errors or prompt injection in a
  RAG pipeline — content trust is a separate concern.
- Deterministic Artifact references make AI Job recovery, provenance, audit, and future browser/RAG workflows
  possible.

---

## 13. English Interview

### Key Vocabulary

presigned URL, bearer credential, bucket, object key, immutable version, ETag, full-object checksum, Upload
Session, Document, ResultArtifact, idempotent finalization, guarded transition, fail-closed, multipart upload,
abort incomplete multipart, reconciliation, composite foreign key, tenant provenance.

### Useful Expressions

- "An upload response is a storage-layer fact, not a verified business fact."
- "The server owns the object identity; the client owns the bytes and declares metadata."
- "I inspect the deterministic object before retrying an unknown external outcome."

### Beginner Question — what is a presigned URL and can you trust the upload?

Real student answer (preserved): "presigned URL is created by object storage,because it must need to give a
expected cheaksum"

Corrected strong answer: "A presigned URL grants temporary, limited permission to upload an object to a
server-defined storage location without exposing long-lived credentials. Before creating a Document, the backend
must verify that the stored object has the expected key, version, size, and checksum, and that it passes the
required security checks. An upload response alone does not prove the object is safe or suitable for business use."

(English corrections: `must need to` -> `must`/`needs to`; `a expected` -> `an expected`; `cheaksum` ->
`checksum`.)

### Intermediate Question — how do you finalize an upload safely and idempotently?

Real student answer (preserved): "the backend must verify that the stored object has the expected key, version,
size, and checksum, and that it passes the required security checks.then completion durable database truth"

Strong answer: "I first inspect and verify the immutable object outside the database transaction. Then I open a
short transaction, lock and re-read the Upload Session, create exactly one Document, and mark the session verified
in the same commit. If a retry finds the session already verified, it returns the existing Document. A unique
constraint on the upload session ID and a guarded state transition prevent duplicates. If the database commit
fails, I verify the same deterministic object again instead of re-uploading it."

(English correction: `then completion durable database truth` -> `Then commit the durable database facts in a short
transaction.`)

### Senior Question — recover an unknown multipart completion while the scanner is down

Real student answer (preserved): "insepect external evidence first,re-read postgresql truth,idempotent guarded
transition,reconciliation instead of bind side-effect retry"

Strong answer: "I first inspect the deterministic object reference to determine whether the multipart completion
actually succeeded; I do not restart the upload just because the response timed out. If the final object exists, I
verify its version, size, and checksum and preserve it for scanning. Because the malware scanner is unavailable, I
fail closed: the session stays in a verification state, no Document is created, and scanning is retried with
bounded backoff. The cleanup worker uses a guarded database transition and must not delete an object that is being
verified or has already produced a Document. After the scanner succeeds, I finalize in a short transaction with a
unique constraint and a guarded transition. Unknown outcomes are reconciled from evidence instead of blindly
retrying external side effects."

(English corrections: `insepect` -> `inspect`; `postgresql` -> `PostgreSQL`; `bind` -> `blind`.)

### Common Weak Answer

"The upload returned 200, so I save the file record and start the Job." — trusts a storage fact as a business
fact, ignores verification, security, versioning, and recovery.

### Strong Answer

See the senior answer above: inspect external evidence, re-read PostgreSQL truth, idempotent guarded transition,
reconcile instead of blind retry.

---

## 14. Mental Model Summary

```text
Upload success        = storage-layer fact
Verified              = business fact + evidence
Upload Session        = temporary server-owned workflow state
Presigned URL         = scoped short-lived bearer credential (not identity, not one-time)
Bucket + key + version= deterministic immutable identity
Document              = durable verified INPUT reference (not bytes)
ResultArtifact        = durable verified OUTPUT reference (not bytes)
Verification          = frozen expected == trusted observed  + security/content gates
Finalization          = verify OUTSIDE db tx -> short guarded UoW creates reference + flips state
Completion vs cleanup = serialize on DB state; never hold a DB lock over storage I/O
cleanup_not_before    = credential expiry + clock skew + safety buffer
Recovery              = inspect evidence -> re-read PG -> idempotent guarded transition -> reconcile
ETag                  != SHA-256
UNIQUE(session)       = at most one Document; composite FK = same-tenant provenance
```

---

## 15. Today's Takeaway

- **Most important mental model:** upload success is a storage fact; verified is a business fact backed by evidence.
- **Most important production risk:** publishing a durable truth (verified/succeeded) with no verified object
  behind it, or feeding unverified/cross-tenant/malicious bytes to a paid AI Job.
- **Most important trade-off:** external-first (recoverable orphan) over DB-first (false success); fail-closed on a
  mandatory scan gate.
- **Most important framework connection:** FastAPI issues scoped credentials and verifies later; it never proxies
  or trusts the raw upload.
- **Most important AI Backend connection:** deterministic verified Artifact references make Provider-result
  publication and crash recovery possible without re-calling a paid Provider.
- **Most important interview answer:** inspect external evidence, re-read PostgreSQL truth, idempotent guarded
  transition, reconcile instead of blind retry.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why storage `200` is not a verified business fact?
- [ ] Can I explain why the server (not the client) owns the object key and version?
- [ ] Can I explain why a presigned URL is not naturally one-time, and how to enforce immutability?
- [ ] Can I run expected-vs-observed verification without rewriting the expectation or trusting an ETag as SHA-256?
- [ ] Can I resolve the completion-vs-cleanup race without holding a DB lock over storage I/O?
- [ ] Can I compute cleanup_not_before (credential expiry + skew + buffer)?
- [ ] Can I recover a timed-out multipart Complete and a crash-before-DB-completion without re-calling the Provider?
- [ ] Can I explain UNIQUE vs the composite FK for tenant provenance?
- [ ] Can I state which evidence levels are and are not proven by fake-adapter tests?
- [ ] Can I answer a beginner, intermediate, and senior interview question in English?
```

---

Engineering artifact + runbook:
[`projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md`](../../projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md).
Runnable model: [`day49_upload_verification.py`](../../projects/ai-backend-data-layer/api/day49_upload_verification.py);
tests: [`test_day49_upload_verification.py`](../../projects/ai-backend-data-layer/api/test_day49_upload_verification.py)
(fake in-memory adapter; **17 passed**; Python 3.10.12, pytest 7.4.3). PostgreSQL / Object Storage / integration /
production validation: **NOT RUN**.
