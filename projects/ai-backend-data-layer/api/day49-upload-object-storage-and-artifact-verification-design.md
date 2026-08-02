# Day49 — Upload Sessions, Object Storage and Artifact Verification (Design + Runbook)

Engineering artifact for `docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md`.
Runnable control-flow model: [`day49_upload_verification.py`](day49_upload_verification.py); tests:
[`test_day49_upload_verification.py`](test_day49_upload_verification.py); deps:
[`requirements-day49.txt`](requirements-day49.txt).

This continues the existing `projects/ai-backend-data-layer/` artifact. It reuses three Day48 boundaries:
schema change spans schema + historical rows + every Writer; external Provider/Object Storage side effects live
OUTSIDE PostgreSQL rollback; unknown outcomes are reconciled from evidence, never blindly retried.

---

## 0. Evidence label (read first)

```text
CONCEPTUAL / CLASSROOM DESIGN : COMPLETED
STATIC DAY49 FILE CHECKS      : RUN (py_compile of module + tests)
FAKE OBJECT STORAGE RUNTIME   : RUN (in-memory adapter; application control flow only)
POSTGRESQL RUNTIME            : NOT RUN (no server/driver)
OBJECT STORAGE RUNTIME        : NOT RUN (no real S3-compatible endpoint)
FASTAPI / SCANNER INTEGRATION : NOT RUN
PRODUCTION VALIDATION         : NOT RUN
```

The fake in-memory adapter proves APPLICATION CONTROL FLOW only. It is NOT proof of real
presigned/checksum/multipart/versioning semantics, NOT PostgreSQL FK/constraint behavior, and NOT a real Object
Storage integration. Day48's evidence is NOT inherited as Day49 evidence.

Executed: `python3 -m pytest -q test_day49_upload_verification.py` -> **17 passed**
(Python 3.10.12, pytest 7.4.3; the module + tests are Python-standard-library only).

---

## 1. Core mental model

```text
Upload success  = storage-layer fact
Verified        = backend business fact supported by evidence

Upload Session  = durable temporary workflow state for ONE server-owned upload identity
Presigned URL   = short-lived, least-privilege BEARER credential for an exact operation (not identity)
Bucket + key + immutable version = deterministic identity of external bytes
Document        = durable verified reusable INPUT reference   (not the bytes)
ResultArtifact  = durable verified OUTPUT reference for a JobAttempt (not the bytes)

Verification = frozen expected contract  ==  trusted observed object evidence
             + content / parser / security / business-policy gates

Safe finalization = external verification OUTSIDE a DB tx
                  -> short PostgreSQL UoW creates the reference + flips state atomically

Recovery = inspect external evidence -> re-read PostgreSQL truth
         -> idempotent guarded transition -> reconciliation, never blind side-effect retry
```

---

## 2. Lifecycle + state ownership

```text
                 client uploads bytes directly to Object Storage (FastAPI never proxies 2 GB)
                                    |
 create Upload Session  --(presigned grant)-->  [initiated] -> [uploading]
   server owns key identity                          |
   freezes expected size/sha256/content-type         |  finalize (idempotent):
                                                      |    inspect+verify OUTSIDE db tx
                                                      |    scan (fail-closed)
                                                      v    short UoW: create Document + flip
                                            [verified] -----------------------------> Document
                                                      |
                        no completion + credential expiry + skew + buffer
                                                      v
                                           [expired] --(guarded)--> cleanup deletes unverified object
```

Three distinct lifecycles (do NOT collapse them):

- **Session expiry** — backend stops accepting business completion.
- **Credential expiry** — Object Storage stops honoring the signed credential.
- **Cleanup eligibility** — credential expiry + bounded clock skew + safety buffer.

`cleanup_not_before = credential_expiry + max_clock_skew + safety_buffer`
(classroom example: 12:00 + 2m + 1m -> **12:03**). Session expiry must not precede credential expiry.

Schema-honesty decision: the published `upload_sessions` status allowlist is
`initiated/uploading/verified/failed/expired` with **no** `verifying` state. This artifact keeps the row
`uploading` until all gates pass, so **no Alembic change** and **no edit to a published CHECK** is needed. Adding a
`verifying` status would be a Day48-safe **forward branch** revision (never a rewrite of published history) if
operational visibility later requires it — intentionally not done here.

---

## 3. Server-owned deterministic identity

The **server** chooses `bucket + key` when creating the session; the client chooses bytes and declares metadata.

```text
key = uploads/{tenant_id}/{upload_session_id}/source     # server-owned; example shape
```

Original filename is untrusted metadata and never controls the internal path. Completion loads the **persisted**
key and rejects a different client-supplied key (`derive_object_key`, `finalize_upload(... client_supplied_key)`
-> `REJECTED_KEY`).

- **Bucket** = top-level namespace/policy/config container — not a filesystem folder.
- **Object key** = identity inside a bucket; `/` is naming convention, not automatically a security boundary.
- **Version** (or an enforced create-only/no-overwrite invariant) pins the exact immutable bytes that were
  verified. A reference is conceptually `bucket + key + version` + verification evidence.

---

## 4. Presigned contracts (single + multipart), no real credential

Least-privilege grant (`create_upload_grant` -> `PresignedGrant`): bind exact operation/method, bucket, EXACT key,
expiry, size policy, expected checksum, allowed content metadata. Never grant list, read-other, delete,
arbitrary-key/prefix write, copy/admin, ACL/policy change, or long-lived service credentials. Treat the URL as a
bearer secret (TLS only, redact query parameters, never persist as Artifact identity). CORS is not authorization.
Short TTL lowers leak/replay risk but conflicts with large slow uploads and is **not immutability proof**.

A presigned URL is **not** naturally one-time — it is normally a replayable bearer credential until expiry. A
one-time completion endpoint does **not** revoke direct Object Storage writes. The invariant is immutable verified
object identity, enforced with a per-session **unique never-reused key** plus **create-only** conditional writes or
versioning + a persisted version ID.

Multipart (2 GB / 45-minute scenario): provider `upload_id`, per-part short-lived credentials, bounded part
numbers/sizes/checksums, selective retry, controlled final Complete/assembly. **Part success = transport progress,
not a final object and not a Document.** Only after Complete/assembly + final-object version/size/full-checksum
verification may scanning begin. Incomplete parts consume storage and require `AbortMultipartUpload` + lifecycle
cleanup.

---

## 5. Expected vs observed verification

```text
expected (frozen in the Upload Session BEFORE upload):  size, sha256, content-type
observed (trusted Object Storage inspection):           bucket, key, version, size, etag, sha256
completion request metadata:                            UNTRUSTED repeated input

verify_object(expected, observed):
  observed is None                       -> MISSING
  observed.version empty                 -> MISMATCH (no immutable version pinned)
  observed.size   != expected.size       -> MISMATCH
  observed.sha256 is None                -> MISMATCH (no trustworthy full-object hash; ETag is NOT a SHA-256)
  observed.sha256 != expected.sha256     -> MISMATCH
  else                                   -> OK
```

Verification **never overwrites the expectation** to make a mismatch pass (the expected contract is a frozen
dataclass). Ordinary **ETag must not be assumed to equal SHA-256** (multipart/encryption change it). FastAPI does
not download 2 GB merely to hash it if the provider can expose a trustworthy full-object checksum; otherwise an
isolated asynchronous verifier may stream the object. Mismatch -> failed/quarantine, **no Document, no Job**.

---

## 6. Content/security scanning boundary

A matching version/size/checksum proves identity/integrity, **not** safety or semantic validity. Layered gates:
storage identity/integrity; real media-type detection from bytes; parser/structure + bounded-resource checks;
malware/decompression-bomb checks in isolation; business/tenant policy. Malware-scan success does not make document
instructions/claims trustworthy for an AI/RAG pipeline.

The 2 GB scan must **not** run inside a FastAPI request transaction. Scanner outage on a **mandatory** gate is
**fail-closed**: keep waiting/verifying with bounded backoff and create no Document (`finalize_upload` ->
`SCAN_RETRY_LATER`, session stays `uploading`). Permanent malicious/invalid content is failed/quarantined
(`SCAN_FAILED` -> `failed`), not retried forever.

---

## 7. Document + ResultArtifact finalization UoWs

**Input (Document).** Object Storage inspection + scanning happen outside a DB transaction. Finalization opens a
short UoW, re-reads/locks the Upload Session, rechecks state/expiry, creates exactly one Document, and flips the
session to `verified` in the same commit. If already verified, return the existing Document. Natural stable
identity = `upload_session_id` + guarded transition + `UNIQUE(documents.upload_session_id)` — distinct from Day50's
tenant-scoped client idempotency key for Job creation. A DB commit failure does **not** justify re-uploading bytes:
retry re-inspects the same deterministic immutable object and retries only the short DB finalization.

**Output (ResultArtifact).** Correct ordering: upload output bytes -> verify immutable Object Storage evidence ->
short UoW inserts ResultArtifact + JobEvent and guardedly marks the Job succeeded. **Never mark a Job succeeded
before its result reference can be committed coherently.** External-first may leave a recoverable orphan on DB
failure; DB-first can publish the false fact `succeeded` while the result is absent.

```text
Document finalize outcomes : CREATED | ALREADY_VERIFIED | VERIFY_FAILED | SCAN_FAILED | SCAN_RETRY_LATER | REJECTED_KEY
Result recovery            : COMPLETE_IDEMPOTENT_NO_PROVIDER | ALREADY_COMPLETED | PRESERVE_UNKNOWN
```

---

## 8. Completion vs cleanup concurrency

Both compete on the same Upload Session DB state via `SELECT ... FOR UPDATE` or a guarded UPDATE.

- Completion commits `verified` + Document first -> cleanup's eligible-state predicate affects zero rows and it
  must not delete the object.
- Cleanup commits `expired` first -> completion's final guarded check fails and creates no Document.
- **Never hold a DB row lock while doing slow Object Storage I/O.** Cleanup commits the durable expired decision
  first, then deletes the exact unverified object/version OUTSIDE the DB tx. Delete failure leaves a recoverable
  orphan rather than a dangling verified fact.

`classify_cleanup` never returns `DELETE_ORPHAN` for a `verified` session or one that already produced a Document
(`KEEP_VERIFIED` / `KEEP_HAS_DOCUMENT`), and returns `KEEP_TOO_EARLY` before `cleanup_not_before`.

Integrated race (Exercise 21): concurrent completion A/B, response lost after A commits, cleanup racing. B
re-reads and returns the existing Document; cleanup's guarded eligible-state UPDATE affects zero rows and does not
delete the verified version.

---

## 9. Unknown-result reconciliation

- **Timed-out `CompleteMultipartUpload`** (`classify_multipart_completion`): inspect the deterministic final
  object first. Exists + matches -> `COMPLETE_SUCCEEDED`. Exists + wrong -> `FINAL_OBJECT_MISMATCH` (quarantine).
  Absent + parts present -> `RECOVER_FROM_PARTS` (inspect the same `upload_id`/parts; do not start a new upload).
  Absent + no parts -> `PARTS_NOT_ASSEMBLED`. Evidence is a bound tuple, not a checksum string in isolation.
- **Crash after verified output upload, before DB completion** (`classify_result_recovery`): do NOT call the paid
  Provider again. Re-read Job/Attempt/Event, inspect the deterministic object; matches ->
  `COMPLETE_IDEMPOTENT_NO_PROVIDER`; missing/inconsistent -> `PRESERVE_UNKNOWN`; already succeeded ->
  `ALREADY_COMPLETED`.

No exactly-once is claimed across PostgreSQL and Object Storage; the guarantee is deterministic identity +
idempotent guarded completion + reconciliation.

---

## 10. Tenant-aware relational integrity

`UNIQUE(documents.upload_session_id)` gives at-most-one Document per session — it does **not** prove same-tenant
provenance. The existing Day31 design uses parent candidate key `UNIQUE(tenant_id, upload_session_id)` plus a child
composite FK `FOREIGN KEY (tenant_id, upload_session_id) REFERENCES upload_sessions(...)` `ON DELETE RESTRICT`.
Composite FK = persistent relationship integrity, **not** request authorization (Day52 supplies authorization).
The in-memory `InMemoryStore.create_document` models both invariants (`DuplicateDocumentError`, `ProvenanceError`).

---

## 11. Cleanup timing + orphan recovery

Store/derive the real signed expiry; do not let session expiry precede credential expiry. Defense in depth:
never-reused staging keys, delayed cleanup, `AbortMultipartUpload`, inventory/reconciliation, and a carefully
scoped Object Storage lifecycle rule. Lifecycle rules must **not** delete verified Documents. A staging->durable
promotion or reliable tag/version policy has operational trade-offs and is not universally best. A failed delete
leaves a recoverable orphan (inventory/reconciliation later), never a dangling verified fact.

---

## 12. Validation / evidence matrix

| Claim | Status | How |
|---|---|---|
| Conceptual design | COMPLETED | this runbook + lesson |
| Static file checks | RUN | `py_compile` module + tests |
| Fake Object Storage runtime | RUN | in-memory adapter, 17 pytest cases (control flow only) |
| Real PostgreSQL FK/constraint runtime | NOT RUN | needs a server + async driver + Day42 raw SQL |
| Real Object Storage (presign/checksum/multipart/versioning) | NOT RUN | needs an S3-compatible endpoint |
| FastAPI/scanner integration | NOT RUN | no request-layer wiring executed |
| Production validation | NOT RUN | — |

`SQLAlchemy metadata inspection proves declaration, not real PostgreSQL FK behavior. Fake adapter tests prove
application control flow, not real presigned/checksum/multipart/versioning semantics.`

---

## 13. Boundaries preserved (not implemented here)

Day50 idempotent Job acceptance + atomic Job/Outbox intent; Day51 authentication; Day52 authorization/tenant
isolation/quota; Day53 real Provider SDK; Day55 Celery worker runtime. This artifact does not implement or claim
any of them, and uses no real S3/Celery/OpenAI integration.
