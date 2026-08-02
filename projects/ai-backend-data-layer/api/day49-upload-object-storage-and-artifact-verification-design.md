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

The fake in-memory adapter proves APPLICATION CONTROL FLOW only, including a **modeled** atomic Unit of Work
(all-or-nothing over two in-memory facts). It is NOT proof of real presigned/checksum/multipart/versioning
semantics, NOT real PostgreSQL FK/constraint/**transaction atomicity**, and NOT a real Object Storage integration.
Three distinct claims are kept separate throughout: **Conceptual Artifact**, **Static/Fake-adapter Verification**,
and **Real Runtime Verification** (the last is NOT RUN). Day48's evidence is NOT inherited as Day49 evidence.

Executed: `python3 -m pytest -q test_day49_upload_verification.py` -> **44 passed**
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
 create Upload Session  --(grant)-->  [initiated] --(bytes uploaded)--> [uploading]
   server owns bucket+key identity                       |
   freezes expected size/sha256/content-type             |  finalize() — GUARDED:
                                                          |   legal-state guard (only uploading/verifying)
                                                          |   re-check session/credential expiry
                                                          |   reject client bucket/key/version
                                                          |   inspect+verify EXACT ref OUTSIDE db tx
                                                          |   scan ---- transient outage -----> [verifying] (hold_until)
                                                          |    | unsafe                              |  retry (bounded backoff
                                                          |    v                                     |   renews the hold)
                                                          | [failed]                                 |  scanner back -> finalize
                                                          v                                          v
                                       ATOMIC short UoW: create Document + flip ----------> [verified] -> Document
                                                          |
   legal-state guard + expiry re-check reject INITIATED/FAILED/EXPIRED and a cleanup-claimed row
                                                          |
             no completion + credential expiry + skew + buffer + NO live verification hold
                                                          v
   cleanup CLAIM commits [expired] FIRST (guarded), THEN deletes the exact unverified object/version outside the tx
```

Three distinct lifecycles (do NOT collapse them):

- **Session expiry** — backend stops accepting business completion.
- **Credential expiry** — Object Storage stops honoring the signed credential.
- **Cleanup eligibility** — credential expiry + bounded clock skew + safety buffer.

`cleanup_not_before = credential_expiry + max_clock_skew + safety_buffer`
(classroom example: 12:00 + 2m + 1m -> **12:03**). Session expiry must not precede credential expiry.

Hardened guards (review round 1):

- **Legal-state guard** — `finalize_upload` proceeds only from `uploading` or `verifying`; `initiated`, `failed`,
  `expired` (including a row a cleanup worker already claimed) are rejected (`ILLEGAL_STATE`).
- **Expiry re-check (Finding 3)** — a hard **workflow** `session_expires_at` stops completion in any state. A
  **credential** expiry does NOT by itself invalidate an object that was already uploaded: after credential expiry
  but before session expiry, completion inspects the server-owned bucket/key and, if the object exists and matches
  the frozen contract, binds the version, scans and completes; if the object is absent it returns
  `UPLOAD_WINDOW_EXPIRED` (credential closed, nothing arrived) or `OBJECT_NOT_FOUND` (credential still valid) — it
  never fabricates a Document.
- **Verification lease (fencing)** — BEFORE scanning, a guarded CAS (`claim_verification`) takes a lease with an
  owner/fencing token + `verification_hold_until` and binds the exact version. The scanner runs with NO DB lock
  held; `classify_cleanup` returns `KEEP_VERIFICATION_HOLD` while the lease is live, so a slow-but-normal scan is
  protected (not only a scanner outage). A dead verifier (deadline passed, not renewed, past the timing gate) is
  bounded-reclaimable, so a transient outage never becomes a permanent business failure while a live retry is
  always protected.
- **Guarded commit (fencing)** — after the scan, `commit_document_if_owner` re-reads and commits ONLY if still
  `VERIFYING`, still owned by this token, not session-expired, and cleanup has not won; a stale worker gets
  `lease_lost` and a cleanup-won row gets `cleanup_won`. `EXPIRED` is never flipped back to `VERIFIED`.
- **Deterministic race (proven by interleaving control-flow tests)** — `claim_cleanup` commits the durable
  `expired` decision FIRST, then returns the exact-version reference; a completion that races it is refused at the
  guarded commit. Determinism is demonstrated by tests whose scanner double calls `claim_cleanup` mid-scan (cleanup
  wins vs completion wins vs live-lease-blocks-cleanup). This is fake-adapter control-flow evidence, NOT real DB
  fencing/`SELECT ... FOR UPDATE`.

Schema-honesty decision (updated after review round 1): the published `upload_sessions` status allowlist is
`initiated/uploading/verified/failed/expired` with **no** `verifying` state. The hardened model needs a
**persistent verification hold** so a transient scanner outage cannot leave a row that cleanup later deletes, so it
**models** a `VERIFYING` state plus a `verification_hold_until` deadline on the session row. In the **real schema**
this requires a Day48-safe **forward** migration (add a `verifying` status via a branch revision, or a separate
verification-hold/lease table) — that migration is **Real Runtime scope and is NOT implemented here**; the in-memory
`VERIFYING` + hold is Static/Fake-adapter (control-flow) evidence only, never a rewrite of published Alembic history.

---

## 3. Server-owned deterministic identity

The **server** chooses `bucket + key` when creating the session; the client chooses bytes and declares metadata.

```text
key = uploads/{tenant_id}/{upload_session_id}/source     # server-owned; example shape
```

The Upload Session persists the **full** server-owned expected reference — `expected_bucket` + `expected_key`
(both chosen by the server at creation) plus the `expected_version` **bound after** the upload is confirmed
(`ExpectedContract`). Completion never trusts client-supplied bucket/key/version: `finalize_upload` rejects any
`client_supplied_bucket`/`client_supplied_key`/`client_supplied_version` that differs from the persisted values
(`REJECTED_IDENTITY`), and inspects the EXACT server-owned reference. `verify_object` compares observed
**bucket, key, version, size, full-object SHA-256, and content-type** against the frozen contract; any identity
mismatch fails.

- **Bucket** = top-level namespace/policy/config container — not a filesystem folder.
- **Object key** = identity inside a bucket; `/` is naming convention, not automatically a security boundary.
- **Version** (plus an enforced create-only/no-overwrite invariant) pins the exact immutable bytes that were
  verified. A reference is conceptually `bucket + key + version` + verification evidence. The fake adapter keeps a
  per-`(bucket, key)` **version history**, defaults to **create-only** writes (a replayed PUT to an existing key
  raises `ObjectAlreadyExistsError`), and inspects/deletes an **exact** version — so a later write to the same key
  can never be verified as the original bytes.

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
**fail-closed**: `finalize_upload` -> `SCAN_RETRY_LATER`, moving the row to `verifying` and taking a
`verification_hold_until` deadline so cleanup will not delete the object while a live verifier keeps retrying with
bounded backoff (each retry renews the hold). A transient outage therefore never becomes a permanent business
failure. Permanent malicious/invalid content is failed/quarantined (`SCAN_FAILED` -> `failed`), not retried forever.

---

## 7. Document + ResultArtifact finalization UoWs

**Input (Document).** Finalization applies the **legal-state guard** and workflow-expiry re-check (section 2),
rejects any client-supplied bucket/key/version (section 3), inspects+verifies the EXACT server-owned reference, then
takes a **verification lease** and **binds the exact version BEFORE scanning** via a guarded compare-and-set
(`InMemoryStore.claim_verification`: owner/fencing token + `verification_hold_until`, version bound unbound->observed).
The scanner runs with **no DB lock held**; a live lease keeps cleanup out. After the scan the clock is re-read and a
second guarded CAS (`InMemoryStore.commit_document_if_owner`) creates exactly one Document AND flips the session to
`verified` **atomically** — but ONLY if the row is still `VERIFYING`, still owned by this token, not
session-expired, and cleanup has not won; otherwise it refuses (`lease_lost` / `cleanup_won` / `session_expired`)
and NEVER flips `EXPIRED` back to `VERIFIED`. All validation + object construction precede the single commit block,
so a failure before commit leaves NEITHER fact (atomicity test). This models transactional atomicity + fencing; it
is **not** proof of real PostgreSQL behavior. If already verified, return the existing Document. Natural stable
identity = `upload_session_id` + guarded transition + `UNIQUE(documents.upload_session_id)` — distinct from Day50's
tenant-scoped client idempotency key. A DB commit failure does **not** justify re-uploading bytes: retry re-inspects
the same deterministic immutable object (the bound version) and
retries only the short DB finalization.

**Output (ResultArtifact).** Correct ordering: upload output bytes -> verify immutable Object Storage evidence ->
short UoW inserts ResultArtifact + JobEvent and guardedly marks the Job succeeded. **Never mark a Job succeeded
before its result reference can be committed coherently.** External-first may leave a recoverable orphan on DB
failure; DB-first can publish the false fact `succeeded` while the result is absent.

```text
Document finalize outcomes : CREATED | ALREADY_VERIFIED | ILLEGAL_STATE | SESSION_EXPIRED | VERIFY_FAILED |
                             SCAN_FAILED | SCAN_RETRY_LATER | REJECTED_IDENTITY
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

`classify_cleanup` never returns `DELETE_ORPHAN` for a `verified` session (`KEEP_VERIFIED`), one that already
produced a Document (`KEEP_HAS_DOCUMENT`), or one with a **live verification lease** (`KEEP_VERIFICATION_HOLD`), and
returns `KEEP_TOO_EARLY` before `cleanup_not_before`. `claim_cleanup` commits the durable `expired` decision FIRST,
then resolves the EXACT version to delete: it uses the bound version, or (if unbound) inspects the server-owned
bucket/key for the exact observed version and PERSISTS that binding — so its returned `CleanupClaim` always carries
a usable exact version (`DELETE_EXACT_VERSION`) or reports `NO_OBJECT_PRESENT`, never a `version=None` delete. The
delete itself is a separate `execute_cleanup_delete` whose result is reconciliation-honest: `DELETED`, or
`VERSION_ABSENT_RECONCILE` when the exact version is already gone (never a false "deleted"). A racing completion is
refused at the guarded commit — determinism is proven by the interleaving control-flow tests.

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
The in-memory store models both invariants: `UNIQUE(documents.upload_session_id)` inside the guarded
`commit_document_if_owner` CAS (`DuplicateDocumentError`), and the composite FK via `assert_document_provenance`
(`ProvenanceError`).

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
| Fake Object Storage runtime | RUN | in-memory adapter, 44 pytest cases (control flow only) |
| Atomic + fenced commit UoW | MODELED (RUN) | guarded CAS `commit_document_if_owner` (owner token + state + expiry), mid-transaction failure test — control flow, not real tx atomicity/fencing |
| Verification lease + completion/cleanup interleaving | MODELED (RUN) | `claim_verification` (owner/hold) + interleaving tests: cleanup-wins, completion-wins, live-lease-blocks-cleanup, stale-lease-refused, retry-renews, dead-verifier-reclaim |
| Exact version bound before scan + version-safe delete | MODELED (RUN) | version bound in `claim_verification`; `claim_cleanup` returns exact version; `execute_cleanup_delete` exact-version/reconcile tests |
| Credential vs session vs cleanup timing (Finding 3) | MODELED (RUN) | complete-after-credential-expiry, upload-window-expired, session-expiry-blocks, boundary tests |
| Real PostgreSQL FK/constraint/tx-atomicity runtime | NOT RUN | needs a server + async driver + Day42 raw SQL + a `verifying`-status forward migration |
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
