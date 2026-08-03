# Day50 — Idempotent AI Job API and Transactional Outbox Integration

## 1. Lesson Metadata

```text
Status: Completed
Template: LESSON_TEMPLATE_v2
Version: 1.0
Difficulty: Advanced
Estimated Time: 5-6 hours
Prerequisite: Day49 — Upload Sessions, Object Storage and Artifact Verification
Previous Lesson: Day49 — Upload Sessions, Object Storage and Artifact Verification
Next Lesson: Day51 — Authentication
Engineering Artifact: projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md
  + runnable day50_job_acceptance_outbox.py + test_day50_job_acceptance_outbox.py (fake in-memory store + transport; 29 passed)
```

Main engineering artifact: a provider-neutral, deterministic idempotent-acceptance + transactional-outbox
control-flow model with a fake in-memory store and TransportAdapter, plus the
[design/runbook](../../projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md).

---

## 2. Learning Objectives

After this lesson you can:

- **Explain** why an `Idempotency-Key` is the identity of one logical client command and why the API — not the
  Provider — is the first thing it protects.
- **Design** a request fingerprint that is evidence the key was not reused for a different command, and decide when
  Document order is behavior-changing.
- **Compare** application `SELECT`-then-`INSERT` with a database `UNIQUE(tenant_id, idempotency_key)` + atomic
  conflict path, and defend why the database is the concurrent arbiter.
- **Implement** one short Unit of Work that persists a Job and exactly one `job.dispatch_requested` Outbox intent
  atomically.
- **Diagnose** the difference between Job+Outbox atomicity (PostgreSQL-local) and at-least-once Relay delivery, and
  why neither claims exactly-once.
- **Recover** an unknown publish result, a transient transport failure, and an exhausted/quarantined dispatch —
  without losing an accepted Job or marking it failed.
- **Apply** relay short-claim + lease + fencing and a Worker guarded claim so duplicate delivery cannot cause two
  Provider calls.
- **Answer** beginner, intermediate, and senior interview questions in English.

---

## 3. Why This Matters

Accepted AI Jobs are expensive and long-running. The classic failure: a client submits a Job for a verified
Document, the API commits Job + Outbox and starts a 202 response — but the response is lost. The SDK and the user
both retry, concurrently. If acceptance is not idempotent, you create two Jobs, two dispatch intents, and
eventually two costly Provider calls for one logical command.

The second failure is silent work loss: if you publish to the queue *inside* the DB transaction (or mark the Job
accepted without a durable dispatch obligation), a crash can leave a Job that is "accepted" but never dispatched, or
a message sent for a transaction that rolled back. The transactional outbox fixes both: the Job and its dispatch
intent commit together in PostgreSQL, and a separate Relay delivers the durable intent at-least-once afterward.
Production risk is duplicate Provider spend, lost jobs, and false "done" signals; this lesson makes acceptance
exactly-once *at the API boundary* and dispatch *durable and at-least-once* without pretending the whole pipeline is
exactly-once.

---

## 4. Roadmap Position

```text
Day49 verified Document (server-owned identity, frozen contract, guarded finalization)
        |
        v
Day50 idempotent Job acceptance + atomic Outbox dispatch intent   <-- you are here
        |
        v
Day51 authentication  ->  Day52 authorization + tenant isolation + quotas
        |
        v
Day55 supported Celery broker transport + Worker ACK/redelivery/runtime recovery
```

### Knowledge Continuity

```text
Previous Knowledge
  Day47 short UoW + guarded transition; Day33 Job+Outbox atomicity; Day34 FOR UPDATE SKIP LOCKED + lease;
  Day41 fencing token; Day49 verified tenant-owned Documents + reconciliation of unknown external outcomes
        |
        v
Current Lesson Concept
  Idempotency-Key + fingerprint; UNIQUE(tenant,key) DB arbitration; atomic Job + one dispatch intent;
  Outbox Relay at-least-once; relay lease/fencing; worker guarded claim
        |
        v
Future Production Usage
  Day51 who may submit; Day52 tenant/quota enforcement; Day53 real Provider; Day55 real Celery transport
```

Day50 accepts Jobs only against Day49-verified, tenant-owned Documents. Its stable identity is the client
`(tenant_id, idempotency_key)` — that is NOT Day49's `upload_session_id` finalization identity. Day50 does not
implement a Celery replacement and does not claim broker/Worker/Provider runtime.

---

## 5. Lesson Map

```text
Idempotency-Key = one logical command
  -> request fingerprint = "same command?" evidence (key is not fingerprint material)
  -> UNIQUE(tenant_id, key) = database arbitration (not SELECT-then-INSERT)
  -> one short UoW: Job + exactly one job.dispatch_requested (atomic)
  -> Outbox = durable dispatch obligation; API never publishes inside the DB tx
  -> Relay: claim (SKIP LOCKED + lease) -> publish OUTSIDE the lock -> fenced checkpoint (published_at)
  -> failure: unknown publish -> retain + retry; transient -> backoff+jitter; exhausted -> quarantine (Job not failed)
  -> duplicate message -> Worker guarded queued->running claim -> one Provider call
  -> NO exactly-once across PostgreSQL + broker + Worker + Provider
```

---

## 6. Core Mental Model

```text
Idempotency-Key = identity of one logical client command
fingerprint     = evidence that the command semantics did not change
UNIQUE(tenant_id, key) = database arbitration of concurrent acceptance

verified Document
-> validate request
-> one short UoW: Job + exactly one dispatch Outbox intent
-> commit together or rollback together

Outbox = durable obligation to attempt dispatch
Relay  = at-least-once delivery, never a proof of Job completion
unknown publish result = retain evidence and retry, not delete or guess

duplicate Queue message -> Worker guarded queued -> running claim -> only one owner may call the Provider
short Relay claim + lease + fencing token -> no long DB lock over transport I/O
No exactly-once across PostgreSQL + broker + Worker + Provider.
```

---

## 7. Main Concepts

### Concept 1: The Idempotency-Key is the identity of one logical command

**Tech Lead Question:** The 202 was lost and the client retries the same submission twice, concurrently. What must
the API return, and what must it NOT do?

**Student Thinking:** A retry is the same command, so it should get the same result, not a new job.

**Student Answer:** "应返回之前的job，不应该" create/dispatch again. (And on the same key generally: "job状态、outbox保持同一个，避免重复产生job".)

**Tech Lead Review:** Correct. Same `(tenant_id, Idempotency-Key)` + same request fingerprint -> return the
original Job; create no second Job and no second dispatch intent. The key identifies one logical command; the client
creates and reuses one key for one command. A server-generated unknown key cannot make an ambiguous retry safe.

**Engineering Thinking:** Idempotency at the API boundary is what stops a lost response from turning into duplicate
downstream (expensive) work.

**Production Example:** An SDK auto-retry plus a user refresh both hit `POST /jobs`; one Job, one Provider call.

**Framework Connection:** `accept_job` -> `RETURNED_EXISTING` for a same-key/same-fingerprint retry; `FastAPI`
requires a client-provided `Idempotency-Key` header.

---

### Concept 2: The fingerprint is evidence the key was not reused for a different command

**Tech Lead Question:** Same key arrives, but the request body changed. Accept it?

**Student Answer:** "拒绝这次请求" — reject with 409, and create no Job or Outbox row.

**Tech Lead Review:** Right. Same key + changed business semantics -> 409 Conflict, no durable facts. The
fingerprint must cover ALL behavior-changing normalized fields: verified Document/Artifact references,
prompt/instruction, model/execution profile, output contract, token/quality options, and API version. The key
itself is not fingerprint material — two different keys with the same body are two accepted commands with the same
fingerprint. Missing/invalid key -> reject before any database write ("是拒绝请求并要求客户端提供").

**Engineering Thinking:** The key is identity; the fingerprint is tamper-evidence that the identity still means the
same command.

**Production Example:** A client bug reuses one key for "summarize" and later "translate"; the 409 prevents silently
returning the wrong Job.

**Framework Connection:** `compute_request_fingerprint(...)`; `accept_job` -> `CONFLICT` / `MISSING_IDEMPOTENCY_KEY`.

---

### Concept 3: Document order — canonicalize only when the contract says it is a set

**Tech Lead Question:** Are `[doc-A, doc-B]` and `[doc-B, doc-A]` the same command?

**Student Answer:** "同一命令，关键取决于里面的文档是否有差异" (initially: same command as long as the documents don't differ).

**Tech Lead Review:** Partly. Canonicalize order ONLY for an explicitly unordered product contract. Preserve order
when order changes prompt/model semantics (e.g. a document sequence fed to the model). Fingerprint every
behavior-changing parameter; do not assume set-equality by default.

**Engineering Thinking:** "Same inputs" is a product decision, not a generic list comparison.

**Framework Connection:** `compute_request_fingerprint(request, unordered_documents=...)` — default preserves order.

---

### Concept 4: The database is the concurrent arbiter, not SELECT-then-INSERT

**Tech Lead Question:** Two concurrent first-time requests with the same key. Why is check-then-create wrong?

**Student Answer:** "需要使用一条命令替代" (use one command instead of check-then-create).

**Tech Lead Review:** Correct instinct. The primary failure of `SELECT` then `INSERT` is NOT overwrite — it is that
BOTH concurrent requests see absence and create duplicates. Enforce `UNIQUE(tenant_id, idempotency_key)` and use an
atomic conflict path (`INSERT ... ON CONFLICT ... RETURNING`) inside the short UoW: the winner creates the Job and
dispatch intent; the loser re-reads the existing Job and compares the stored fingerprint. PostgreSQL is the final
arbiter.

**Engineering Thinking:** Concurrency correctness belongs in a database constraint, not in application timing.

**Hardened (review round 1, P1-1):** the conflict decision must live INSIDE the atomic op, not in a separate
`find_by_idempotency` read followed by an unconditional insert. `upsert_job_on_conflict` re-checks and creates in one
critical section (a lock in the fake store; the UNIQUE index in real PostgreSQL), so two concurrent requests that
both read absence still produce exactly one `CREATED` and one `RETURNED_EXISTING` — one Job and one dispatch intent.
A forced-interleaving thread test proves it; the outer existence read is only a fast path.

**Framework Connection:** `store.upsert_job_on_conflict(...)` models `INSERT ... ON CONFLICT (tenant_id,
idempotency_key) DO NOTHING RETURNING`; the published `app.jobs` schema already has `UNIQUE(tenant_id,
idempotency_key)`.

---

### Concept 5: One short UoW — Job + exactly one dispatch intent, atomic

**Tech Lead Question:** How do you guarantee an accepted Job always has a durable dispatch obligation?

**Student Answer:** "原子事务提交" — and the failure-test idea: "原子事务提交只有job没有outbox intent" (inject a failure so
only the Job would commit) to prove atomicity; one intent via "使用unique(job_id,dispatch intent)".

**Tech Lead Review:** Exactly. Validate the referenced Documents are verified + tenant-owned, then create the Job
and one `job.dispatch_requested` Outbox intent in the SAME transaction — commit both or roll back both. Never return
202 for a Job with no durable dispatch intent. Enforce at-most-one dispatch intent per Job (logical
`UNIQUE(job_id, event_type)`). Unverified/cross-tenant Documents must be rejected ("不能").

**Engineering Thinking:** Atomicity turns "accepted" and "will be dispatched" into a single fact.

**Hardened (review round 1, P1-3):** the mutable Document admission check runs ONLY for a NEW command. An exact
retry of an already-accepted command (same key + same fingerprint) returns the original Job BEFORE re-validating
Documents, so a Document that later becomes unavailable does not break the idempotent retry contract; a genuinely
new command (new key) against that unavailable Document is still rejected.

**Framework Connection:** `upsert_job_on_conflict(fail_before_commit=...)` proves neither commits on failure;
`add_dispatch_intent` raises `DispatchIntentExists` for a second intent.

---

### Concept 6: Outbox + Relay — at-least-once, `published_at` is only a checkpoint

**Tech Lead Question:** Who calls the transport, and when? What does `published_at` prove?

**Student Answers:** "事务提交后由 Relay 调用" (Relay calls it after commit); Relay success checkpoint is
`published_at`; queue payload should be "携带一个尽量小的稳定引用" (a small stable reference).

**Tech Lead Review:** Right. The API UoW never calls the broker inside its DB transaction. After commit, the Relay
reads durable unpublished Outbox intent and publishes through a small `TransportAdapter.publish(envelope)` seam. The
envelope is small and stable (`outbox_event_id`, `event_type`, `job_id`, correlation id) — the queue is not Job
truth; the Worker re-reads the Job by `job_id`. `published_at` is only the Relay publication checkpoint; it does NOT
prove Worker claim, Provider call, or Job success.

**Engineering Thinking:** Separating "durable obligation" (Outbox) from "delivery" (Relay) is what makes acceptance
and dispatch independently recoverable.

**Framework Connection:** `run_relay_once` -> `build_envelope` -> `TransportAdapter.publish`; `published_at` set only
by the fenced checkpoint.

---

### Concept 7: Unknown publish result — retain and retry (at-least-once), do not guess

**Tech Lead Question:** Publish succeeds but the Relay crashes before recording `published_at`. Re-send?

**Student Thinking (initial):** Prevent duplicate work — don't send again.

**Student Answer (initial):** "应该放弃二次传递信息到queue" (give up re-sending).

**Tech Lead Review:** This is the key correction. The publish outcome is *unknown*. Retain the Outbox intent
(`published_at IS NULL`) and publish again on recovery. At-least-once duplicate delivery is safer than silently
losing an accepted Job; the Worker's guarded claim absorbs the duplicate. For a transient failure, keep the event,
increment the attempt count, store a redacted error, compute `next_attempt_at` with bounded exponential backoff +
jitter, and retry later. After timeout, retain: event identity/payload/reference, `published_at=NULL`, incremented
attempt count, redacted last error, next retry time ("使用exponential backoff"). Do not delete and do not claim
success.

**Engineering Thinking:** Under uncertainty, prefer a recoverable duplicate over an unrecoverable loss.

**Framework Connection:** `CrashAfterPublishTransport` leaves `published_at NULL` -> a later pass republishes
(duplicate); `FailingTransport` -> attempt/error/`next_attempt_at` retained.

---

### Concept 8: Exhausted/quarantined dispatch does not fail the Job

**Tech Lead Question:** Dispatch keeps failing past the policy. Do you mark the Job failed?

**Student Answer:** "不是，因为可以受控重放" (no — because it can be controlled-replayed).

**Tech Lead Review:** Correct. On permanent/exhausted failure, retain the original intent + evidence in a visible
quarantined/dispatch-failed state, alert, fix, and controlled-replay. Never delete it silently and never mark the
Job failed merely because dispatch has not completed. Job failure is a guarded business-execution terminal state; a
quarantined Outbox means an accepted Job still needs operational recovery.

**Framework Connection:** `run_relay_once(..., max_attempts=N)` -> `OutboxState.QUARANTINED`, Job stays `queued`.

---

### Concept 9: Relay concurrency — short claim + lease + fencing, no lock over I/O

**Tech Lead Question:** Multiple Relay processes. How do you avoid double publishing and avoid holding a DB lock
across the network call?

**Student Answers:** "使用锁for update skip lock" (multi-relay claim); no lock over publish: "不能，因为如果出现错误会造成死锁";
stale relay: "不能，因为通过fencing token将拒绝A继续标记".

**Tech Lead Review:** Right, and let's sharpen the "why". Use short DB claims (`FOR UPDATE SKIP LOCKED`) with a
recoverable lease/owner token; publish OUTSIDE the DB transaction. Deadlock is possible, but the deeper reason not
to hold a lock across transport I/O is that long uncertain external I/O expands the transaction, blocks Relay
progress, causes lock waits/timeouts, harms availability — and cannot create a cross-system transaction anyway. A
fencing token guards the checkpoint write: a stale Relay whose lease expired cannot write `published_at` after a new
owner has taken over.

**Hardened (review round 1, P1-2):** a fencing check must require a LIVE lease, not just a matching owner. Both
`checkpoint_published_if_owner` and `record_transport_failure` require owner match AND `now < relay_hold_until`, so
a Relay whose lease merely EXPIRED — even before any new owner takes over — is rejected with `FencingError` and
cannot write `published_at`. Otherwise a paused Relay could wake up after its lease lapsed and stamp a stale
checkpoint.

**Framework Connection:** `claim_outbox_batch` (SKIP LOCKED + lease), `checkpoint_published_if_owner` /
`record_transport_failure` raise `FencingError` for a superseded OR expired lease; publish happens between claim and
checkpoint, never inside a lock.

---

### Concept 10: Worker guarded claim absorbs duplicate delivery

**Tech Lead Question:** The same message is delivered twice. How do you ensure only one Provider call?

**Student Answers:** first "idempotency key", refined to "数据库 queued -> running 的守卫更新成功时" (execution authority = a
successful guarded queued->running update). Integrated: one Worker gets one `RETURNING` row, the other gets zero.

**Tech Lead Review:** Correct after refinement. Duplicate queue delivery is allowed. A Worker earns execution
authority only with a guarded `UPDATE ... WHERE job_status='queued' RETURNING`; zero rows means no Provider call.
The four idempotency layers are different: client `(tenant_id, idempotency_key)` protects acceptance; Outbox event
identity protects dispatch intent; the guarded Job claim protects Worker execution; a stable provider
correlation/evidence protects post-call recovery (Day53). Day50 records the provider boundary but does not implement
real Provider runtime.

**Framework Connection:** `worker_claim(job_id)` -> True for one winner, False (zero rows) for duplicates.

---

## 8. Common Misconceptions

Publish-then-crash before `published_at`
❌ Do not re-send, to avoid duplicate work.
✅ The publish result is unknown; retain the intent and republish. At-least-once duplicate delivery + a Worker
   guarded claim is safer than silently losing an accepted Job.

"One idempotency key handles everything"
❌ A single key protects all duplicate layers.
✅ Client `(tenant_id, key)` protects acceptance; Outbox event identity protects dispatch intent; guarded Job claim
   protects Worker execution; provider correlation/evidence protects post-call recovery.

SELECT-then-INSERT
❌ The risk is concurrent requests overwriting each other.
✅ The primary risk is both seeing absence and creating duplicates; `UNIQUE` + atomic conflict handling is the
   arbiter.

Holding the DB lock while publishing
❌ It is rejected mainly because it deadlocks.
✅ Deadlock is possible, but the deeper reason is that long external I/O expands the transaction, blocks Relay
   progress, causes lock waits/timeouts, and cannot create a cross-system transaction.

Document order
❌ `[A,B]` and `[B,A]` are always the same if the documents do not differ.
✅ Canonicalize order only for an explicitly unordered contract; preserve it when order changes model semantics.

Key reuse
❌ Reusing a key causes a database overwrite.
✅ `UNIQUE` blocks overwrite while evidence is retained; the real risk is an expired record letting a late retry be
   treated as a new command — retention is an explicit API contract.

"An existence read before the insert is enough for idempotent acceptance" (review round 1)
❌ `find_by_idempotency` then an unconditional insert.
✅ Two concurrent requests both read absence and both insert. The conflict decision must live INSIDE one atomic op
   (`INSERT ... ON CONFLICT` / a lock); the read is only a fast path.

"A matching owner token means the Relay may checkpoint" (review round 1)
❌ Check only `relay_owner`.
✅ Require a LIVE lease: owner match AND `now < relay_hold_until`. An expired lease is fenced even before a new owner
   takes over, so `published_at` is never stamped by a stale Relay.

"Re-validate Documents on every acceptance, including retries" (review round 1)
❌ Validate Documents first, then check the idempotency key.
✅ For an exact retry (same key + same fingerprint), return the original Job BEFORE the mutable Document admission
   check; validate Documents only for a new command.

"at-least-once" as the atomicity mechanism
❌ The outbox is atomic because delivery is at-least-once.
✅ Job+Outbox atomicity is one PostgreSQL transaction; at-least-once is separate Relay/transport delivery semantics.

`published_at` means done
❌ `published_at` proves the Job was processed.
✅ It is only the Relay publication checkpoint — not Worker claim, Provider call, or Job success.

---

## 9. Engineering Trade-offs

```text
Client-supplied Idempotency-Key  vs  Server-generated key
Client: a retry reuses the same key -> safe dedup. Required here.
Server: a fresh unknown key per call cannot make an ambiguous retry safe -> rejected as the primary mechanism.

DB UNIQUE + ON CONFLICT  vs  application SELECT-then-INSERT
DB arbiter: correct under concurrency (both-create is impossible). Chosen.
App check: duplicates under race; rejected.

Publish inside the API transaction  vs  Transactional Outbox + Relay
Inside tx: a message can be sent for a rolled-back tx, or the tx expands over network I/O. Rejected.
Outbox + Relay: atomic obligation, delivery after commit, recoverable. Chosen. (Cost: at-least-once duplicates.)

At-least-once  vs  "exactly-once"
At-least-once: duplicates possible, absorbed by the Worker guarded claim. Honest and achievable. Chosen.
Exactly-once across PG+broker+Worker+Provider: not claimed; would be a false guarantee.

Quarantine a failed dispatch  vs  mark the Job failed
Quarantine: retain + alert + controlled-replay; the accepted Job is preserved. Chosen.
Mark failed: destroys an accepted Job for an operational transport problem. Rejected.
```

---

## 10. Hands-on Exercises

### Exercise 1: Lost-202 concurrent retry

Question: derive the outcome of two concurrent retries of one command.
Expected Output: one Job, one dispatch intent, the original Job returned, no second event.
Follow-up: what does the loser compare? (the stored fingerprint.)

### Exercise 2: Same key, different fingerprint

Expected Output: 409 Conflict, no new durable facts.
Follow-up: is the key part of the fingerprint? (No.)

### Exercise 3: Atomicity failure injection

Question: force the Outbox write to fail.
Expected Output: neither the Job nor the intent commits.

### Exercise 4: Fake transport timeout

Expected Output: the event is retained, `published_at IS NULL`, attempt/error/next-retry updated, and it becomes
eligible again after `next_attempt_at`.

### Exercise 5: Integrated failure/rollback (design judgment)

Question: Relay A publishes and pauses; its lease expires; Relay B takes over and checkpoints; A's fencing-token
checkpoint is attempted; duplicate messages arrive; two Workers race.
Expected Output: A's stale checkpoint is rejected (`FencingError`); the message is delivered at-least-once
(duplicate); exactly one Worker gets `queued -> running RETURNING`.
Follow-up: why is the duplicate acceptable?

### Exercise 6: Compute the next retry time

Question: bounded exponential backoff with jitter, base 1s, cap 300s.
Expected Output: attempt 1 ~ base; attempt 10 capped at 300s (+ jitter); always <= cap + jitter.

---

## 11. Relevant Framework Connections

- **FastAPI** — `POST /jobs` requires a client `Idempotency-Key`, validates before side effects, returns the
  original Job for a same-key/same-fingerprint retry, rejects a mismatch with 409, and does NOT publish in the
  request UoW.
- **PostgreSQL / SQLAlchemy / Day47 UoW** — `UNIQUE(tenant_id, idempotency_key)`, atomic conflict handling, one
  short Job+Outbox transaction, a guarded Worker claim; an honest split between fake control-flow tests and real
  PostgreSQL proof.
- **PostgreSQL concurrency / Day34** — `FOR UPDATE SKIP LOCKED`, a short claim transaction, lease recovery, and no
  lock held across external I/O.
- **Redis / Celery** — future transport/Worker connection only. Day50 does NOT implement Redis Streams as a Celery
  substitute and does NOT claim Celery runtime; Day55 owns the supported broker transport, ACK/redelivery, and
  poison-task behavior.

---

## 12. AI Backend Connections

- Accepted AI Jobs can be expensive and long-running; a lost 202 must not create duplicate Provider spend.
- Day49 verified Documents are the only accepted input references; raw upload/session facts are not safe Job inputs.
- Queue transport is not business truth; the PostgreSQL Job/Outbox state is durable truth.
- Duplicate Worker messages must not make two costly Provider calls — a guarded claim plus later provider
  correlation/reconciliation (Day53) are required.
- A quarantined dispatch is an operational/recovery problem, not a fabricated AI execution failure.

---

## 13. English Interview

### Key Vocabulary

idempotency key, request fingerprint, unique constraint, `INSERT ... ON CONFLICT`, transactional outbox, dispatch
intent, relay, at-least-once, `published_at` checkpoint, `FOR UPDATE SKIP LOCKED`, lease, fencing token, guarded
claim, quarantine, exactly-once (and why it is not claimed).

### Beginner Question — what is an idempotency key, and why is it useful for an async AI Job API?

Real student answer (preserved): "it avoid to provider call twice"

Correction: "it avoids calling the Provider" — and API acceptance comes first.

Strong answer: "An idempotency key identifies one logical client request. If the client retries after a timeout, the
API returns the original Job instead of creating a duplicate Job and dispatch intent. This helps prevent duplicate
downstream processing."

### Intermediate Question — how does the transactional outbox prevent a Job accepted-but-never-dispatched?

Real student answer (preserved): "use at-least one"

Correction: "at-least-once delivery" is Relay/transport semantics, not the Job+Outbox atomicity mechanism.

Strong answer: "The API creates the Job and its dispatch Outbox event in the same database transaction, so either
both commit or neither does. After the commit, a Relay reads the durable Outbox event and publishes it. Delivery is
at least once, so duplicates are possible, but an accepted Job never silently loses its dispatch intent."

### Senior Question — a Relay publishes successfully but crashes before `published_at`. Recover without losing the Job or calling the Provider twice.

Real student answer (preserved): "relay scan published_at=null row,publish repeat.it avoid lose this job,then two
worker attempt transit queued to running,just one worker can return one row"

Correction: improve grammar and distinguish Relay retry, Worker claim, stale-Relay fencing, and the Provider
recovery boundary.

Strong answer: "The Relay scans Outbox rows where `published_at` is null. If it crashed after publishing but before
the checkpoint, it publishes again, because the result is unknown and the Job must not be lost — duplicate messages
are acceptable. Both Workers attempt a guarded `queued` to `running` update, but only one update returns a row, so
only that Worker may call the Provider. A lease and fencing token also stop a stale Relay from writing a later
checkpoint."

### Common Weak Answer

"I use one idempotency key everywhere and at-least-once, so it's exactly-once." — conflates four different
idempotency layers and claims a guarantee the system does not provide.

### Strong Answer

See the senior answer: durable identity, guarded transitions, idempotent recovery, and evidence retention — with no
exactly-once claim across PostgreSQL, broker, Worker, and Provider.

---

## 14. Mental Model Summary

```text
Idempotency-Key      = identity of one logical command
fingerprint          = evidence the command semantics did not change (key not included)
UNIQUE(tenant,key)   = DB arbitration of concurrent acceptance
Job + dispatch intent= one atomic short UoW (both or neither)
Outbox               = durable obligation to attempt dispatch
Relay                = at-least-once delivery; published_at = checkpoint, not success
unknown publish      = retain + retry (duplicates OK), never delete/guess
transient failure    = attempt++ + redacted error + backoff+jitter next_attempt_at
exhausted            = quarantine (retain), do NOT fail the Job
relay concurrency    = SKIP LOCKED claim + lease + fencing; no lock over transport I/O
duplicate message    = Worker guarded queued->running -> one Provider call
NOT exactly-once     = durable identity + guarded transitions + idempotent recovery + evidence retention
```

---

## 15. Today's Takeaway

- **Most important mental model:** the key is the identity of one command; the fingerprint is evidence it didn't
  change; the database `UNIQUE` is the arbiter.
- **Most important production risk:** a lost 202 turning into duplicate Jobs and duplicate paid Provider calls — or
  an accepted Job with no durable dispatch intent.
- **Most important trade-off:** transactional Outbox + at-least-once Relay over publish-in-transaction or a false
  exactly-once claim.
- **Most important framework connection:** the API UoW never calls the transport; the Relay does, after commit,
  outside any DB lock.
- **Most important AI Backend connection:** duplicate delivery must not cause two Provider calls — a Worker guarded
  claim earns the single execution authority.
- **Most important interview answer:** inspect `published_at IS NULL`, republish (at-least-once), one Worker wins the
  guarded claim, and a fencing token blocks a stale Relay.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why the Idempotency-Key is the identity of a logical command, and the fingerprint is separate?
- [ ] Can I explain why UNIQUE(tenant_id, key) + ON CONFLICT beats SELECT-then-INSERT under concurrency?
- [ ] Can I persist a Job + exactly one dispatch intent atomically, and prove it with a failure-injection test?
- [ ] Can I explain why the API never publishes inside the DB transaction, and what published_at does/does not prove?
- [ ] Can I recover an unknown publish result, a transient failure, and an exhausted dispatch without failing the Job?
- [ ] Can I explain relay short-claim + lease + fencing and why no DB lock is held over transport I/O?
- [ ] Can I explain how a Worker guarded claim absorbs duplicate delivery into one Provider call?
- [ ] Can I state why exactly-once across PostgreSQL + broker + Worker + Provider is not claimed?
- [ ] Can I answer a beginner, intermediate, and senior interview question about this in English?
```

---

Engineering artifact + runbook:
[`projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md`](../../projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md).
Runnable model: [`day50_job_acceptance_outbox.py`](../../projects/ai-backend-data-layer/api/day50_job_acceptance_outbox.py);
tests: [`test_day50_job_acceptance_outbox.py`](../../projects/ai-backend-data-layer/api/test_day50_job_acceptance_outbox.py)
(fake in-memory store + transport; **29 passed**; Python 3.10.12, pytest 7.4.3). PostgreSQL / broker / Celery /
Worker / Provider / integration / production runtime: **NOT RUN**.
