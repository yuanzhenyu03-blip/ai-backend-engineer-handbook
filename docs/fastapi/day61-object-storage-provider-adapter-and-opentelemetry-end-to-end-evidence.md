# Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence

## 1. Lesson Metadata

```text
Status:        Artifacts + EXECUTED_LOCAL_RUNTIME delivered; local INTEGRATION_RUNTIME NOT RUN (not yet marked Completed)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Advanced
Estimated Time: 4 hours
Prerequisite:  Day59 durable HTTP acceptance, Day60 Outbox/Worker/lease/recovery
Next Lesson:   Day62 — Playwright Runtime, Locators and Reliable Async Interaction
```

Day61 turns the Day59 acceptance boundary and Day60 Outbox/Worker recovery boundary into a
real local end-to-end EVIDENCE path: a deterministic fake Provider over real HTTP, Object
Storage artifacts, durable external-operation checkpoints, and OpenTelemetry correlation.

> Evidence honesty: the runtime artifacts are real, and the pure-logic + a REAL
> HTTP-loopback test (the separate fake Provider ↔ the adapter, success/invalid/timeout)
> pass — **19 passed, `EXECUTED_LOCAL_RUNTIME`** (incl. the review fixes: Result-bytes
> metadata is COMPUTED from the actual canonical bytes so a correct success verifies as
> VERIFIED; every external action + state change is fenced by the CURRENT `lease_token`;
> `provider_request_id` is immutable (NULL->set / same->idempotent / different->conflict);
> and a minimal OpenTelemetry layer — `day61_telemetry.py` — adds spans + a low-cardinality
> outcome metric with a no-op fallback). But the full local `INTEGRATION_RUNTIME` matrix
> (PostgreSQL + Redis/Celery + MinIO + OTel Collector) has **NOT been executed** by the
> updating agent (no Docker), so Day61 is **not marked Completed**. See the
> design/runbook's Required integration rerun matrix. Target tier is local
> `INTEGRATION_RUNTIME`, never Production; Day61 never calls a real/paid model Provider.

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain why a Provider HTTP timeout is not proof of non-execution, and why a pre-call
  `provider_dispatch_started_at` marker plus a post-call `provider_request_id` are both
  durable checkpoints.
* Distinguish our stable correlation/idempotency key from the Provider's `provider_request_id`.
* Design a deterministic per-Attempt Result Artifact key and verify it by HEAD (not GET).
* Decide non-overwrite behaviour on checksum/metadata conflict and forward-repair on
  upload-timeout-then-matching-HEAD.
* Gate final success on ONE guarded PostgreSQL transaction under the CURRENT `lease_token`.
* Propagate OpenTelemetry correlation without making it a transactional prerequisite or a
  high-cardinality metric label.
* Classify timeout / invalid-200 / valid outcomes and label evidence tiers honestly.

---

## 3. Why This Matters

Long-running, billable AI Provider operations can time out AFTER being accepted. If the
backend treats a timeout, an HTTP 200, an object's existence, or a Celery ACK as "success",
it will double-bill a model, lose the reconciliation handle, or mark a Job succeeded with no
verifiable output. Day61 makes external work RECOVERABLE and AUDITABLE: durable
external-operation identities, verifiable object artifacts, and correlation that survives
Worker loss — with PostgreSQL, not telemetry or transport, as business truth.

---

## 4. Roadmap Position

```text
Day59 durable HTTP acceptance
      |
      v
Day60 Outbox delivery, Worker authority, lease fencing, recovery
      |
      v
Day61 external Provider/Storage evidence + telemetry across real processes (this lesson)
      |
      v
Day62 Playwright runtime uses this proven backend path · Day63 per-tenant BrowserContext isolation · Day64 browser artifacts into this Object Storage
      |
      v
Interview readiness: timeout semantics, checkpoints, HEAD verification, lease-guarded completion, telemetry-vs-truth
```

### Knowledge continuity

Day59 made `202` a committed PostgreSQL acceptance bundle. Day60 added the real Outbox ->
Redis/Celery -> Worker boundary: broker delivery is not execution authority; the guarded
PostgreSQL claim + lease owner/token/expiry fencing is, and `published_at`/ACK are not
business truth. Day61 keeps all of that and adds the external Provider/Storage/telemetry
evidence layer.

---

## 5. Lesson Map

```text
timeout != non-execution  ->  pre-call marker + post-call request_id  ->  correlation key vs provider_request_id
   ->  per-Attempt Artifact key + HEAD verify + non-overwrite conflict  ->  lease-guarded ONE-tx completion
   ->  OTel correlation (not truth; low-cardinality; exporter failure tolerant)  ->  outcome classification + recovery
```

---

## 6. Core Mental Model

```text
timeout            != Provider did not execute   (marker -> pending_reconciliation, never blind retry)
HTTP 200           != success                    (verify the Result Artifact by HEAD)
object exists / ACK / trace != success           (success = ONE guarded tx under the CURRENT lease_token)
provider_request_id (Provider-minted, post-call) vs correlation key (ours, pre-call)  — distinct, complementary
OTel               = diagnostic correlation, NOT business truth
```

---

## 7. Main Concepts

### Concept 1: A timeout is not non-execution

Tech Lead Question: The Provider call times out. Can the Worker just retry?

Student Thinking / Answer: **"不能，收到了 provider_request_id 进入 PENDING_RECONCILIATION。"**
(No; once we hold a `provider_request_id`, go to `PENDING_RECONCILIATION`.)

Tech Lead Review: Correct direction. A timeout does not prove the Provider did not receive or
execute the request, so never blind-retry a potentially billable call. With a durable
dispatch marker the timeout outcome is `pending_reconciliation`. (Even without a
`provider_request_id` yet — the marker alone is enough to forbid a blind retry.)

### Concept 2: Pre-call marker and post-call request id

Tech Lead Question: What must be durable before, and after, the Provider HTTP call?

Student Thinking / Answer: **"dispatch marker"** before the call; **"provider_request_id"** as
the next durable fact after the response.

Tech Lead Review: Exactly. Persist `provider_dispatch_started_at` BEFORE the call — a pre-call
checkpoint (external work may happen after it; it is not success). Persist
`provider_request_id` as soon as the Provider returns it and BEFORE the ordinary
Artifact/success path. The student first thought the Worker could continue to the Artifact
even if persisting `provider_request_id` failed; corrected: it must durably persist the
external-operation identity first, else a crash loses the precise reconciliation handle and
the success path must not continue (retry only the local checkpoint, else reconcile).

### Concept 3: Correlation key vs provider_request_id

Tech Lead Question: Are our idempotency key and the Provider's request id the same thing?

Student Thinking / Answer: reuse the original stable key for retries of the same Attempt.

Tech Lead Review: Right. OUR stable correlation/idempotency key is created BEFORE the call and
reused for retries of the SAME Attempt; the Provider mints `provider_request_id` AFTER it
receives/accepts the operation. They are distinct and complementary — the correlation key lets
us ask "did you receive this?"; the `provider_request_id` locates the external execution.

### Concept 4: Job vs Attempt, and the per-Attempt Artifact key

Tech Lead Question: One Job, one key?

Student Thinking / Answer: use a stable deterministic key PER Attempt; one Job may have several
Attempts and distinct Artifact keys.

Tech Lead Review: Correct. A `Job` is one durable business request; it can have several
`Attempt`s over its life, but normal execution has ONE authoritative Attempt at a time via the
lease token (a broker duplicate is not automatically a new Attempt). The Result Artifact key is
deterministic PER-ATTEMPT — `results/{tenant_id}/{job_id}/{attempt_id}/result.json` — so the
same Attempt resumes safely against the same key while different Attempts never overwrite.

### Concept 5: Object Storage vs PostgreSQL; HEAD verification

Tech Lead Question: Upload returned 200 — done?

Student Thinking / Answer: the object response should keep only needed/allowed business data
and require validation. (The student initially tied MinIO's need to `provider_request_key`.)

Tech Lead Review: Corrected: Provider identity and Object Storage have DISTINCT roles —
Provider identities locate external execution; Object Storage stores independently durable,
verifiable RESULT BYTES; PostgreSQL owns business truth + Artifact metadata/reference (key,
checksum, size, content type, provenance, timestamps). Upload success is not enough: verify the
deterministic key with HEAD — an HTTP metadata-only retrieval (unlike GET which fetches bytes)
— for existence, checksum, size and content type. On upload-timeout-then-matching-HEAD, forward-
repair the reference (no overwrite). On checksum/metadata mismatch, CONFLICT: no overwrite, no
success, preserve evidence, reconcile. A DB rollback after upload does not undo Object Storage.

### Concept 6: Guarded completion under the current lease token

Tech Lead Question: What actually makes a Job "succeeded"?

Student Thinking / Answer: before a repeat call, check Job/Attempt/Event/reservation/deadline
and durable external evidence; database facts determine business completion.

Tech Lead Review: Final success is ONE guarded PostgreSQL transaction under the CURRENT matching
`lease_token`: verified Artifact reference + Attempt finished/final outcome + success Event tied
to the Attempt + Job `running -> succeeded` + lease cleanup. Object existence, HTTP 200, Celery
ACK and traces alone are NOT success. A stale Worker (superseded token) can upload an object but
CANNOT complete — its guarded UPDATE matches zero rows; preserve such objects for
reconciliation/audit, do not immediately delete them (the student answered this correctly).

### Concept 7: OpenTelemetry is correlation, not truth

Tech Lead Question: Should the full `provider_request_id` go into traces? What if the exporter
dies?

Student Thinking / Answer: the student first said `provider_request_id` was not needed in OTel,
then refined: the full id should not be recorded unconditionally in logs/traces
(sensitive/capability risk); PostgreSQL owns the complete protected value while telemetry uses
approved low-risk correlation such as `job_id`/`attempt_id` and possibly a hash. Reuse the
original trace association for a Relay retry.

Tech Lead Review: Correct. Propagate/persist async trace context HTTP -> Job/Outbox -> Relay ->
Worker; reuse the trace association for the SAME durable Outbox intent on Relay retry, while
every actual operation gets a new span id (`trace_id` = a trace; `span_id` = one operation;
Span Links are optional non-parent/child associations). Metrics use low-cardinality labels
(provider, outcome) — never `job_id`/`attempt_id`/`provider_request_id`. A Collector/exporter
failure must NOT roll back a committed Job or cause another Provider request; emit bounded
exporter diagnostics and state the telemetry limitation — business evidence is reconstructable
from PostgreSQL, Object Storage and Provider identity.

Production Example: an OTLP exporter outage during a valid run. The Job still commits under its
lease token; the trace is simply incomplete, flagged by exporter health metrics, and the
evidence pack is rebuilt from DB + MinIO + the Provider ledger.

Implementation note: telemetry instrumentation swallows ONLY its own errors (SDK init, span
creation, attribute setting, export) — a business exception inside a span propagates unchanged.
The SDK exporter is optional, idempotent and disabled by default (`init_telemetry()`), reads its
endpoint from `OTEL_EXPORTER_OTLP_ENDPOINT` (no hardcoded URL/token), and W3C trace context rides
the existing Outbox `payload` (no migration) from HTTP acceptance through the Relay into the
Worker. A real OTLP export to a running Collector is INTEGRATION_RUNTIME (NOT RUN).

Wiring note: the trace context is now carried end to end — acceptance injects `traceparent` into the
dispatch Outbox payload; the Relay forwards it (outside the DB lock) into the Celery task kwargs; the
Worker extracts it and runs its Provider/Storage/DB spans under that context, so they continue the
original trace. A Relay retry of the same durable intent reuses the same trace association. Telemetry
is bootstrapped at real process start (FastAPI lifespan, Relay `main`, Celery `worker_process_init`),
idempotent and disabled by default. And a stale Worker whose lease was superseded after the HTTP
response returns `lease_lost_no_commit` — it never reports a `pending_reconciliation`/`failed`
transition the database did not make.

Authoritative-path note: the real Celery task runs `run_authoritative_attempt`
(`day61_worker_runtime`), which does the guarded claim, reads the tenant + stable correlation
key from PostgreSQL durable facts (never the Celery message), then calls `run_external_operation`
under the claim's lease token and returns its outcome verbatim. A Job reaches `succeeded` ONLY
after a real Provider HTTP call + Object Storage PUT/HEAD + guarded completion — there is no
"no-Provider, straight-to-succeeded" production path (the Day60 `run_worker_attempt` skeleton is
teaching-only). And acceptance opens a `fastapi.accept_job` ROOT span so a trace actually starts
and its `traceparent` is written into the Outbox payload in the same transaction.

### Concept 8: The deterministic fake Provider (a separate process)

Tech Lead Review: The fake Provider must be a SEPARATE process, not an in-process mock, so it
verifies real HTTP serialization, timeout, header/context propagation and an independent request
ledger. It is IDEMPOTENT on our stable `X-Correlation-Key`: the first request for a key mints ONE
external operation (one `provider_request_id` + one result); a same-key retry returns that exact
result WITHOUT a second execution, and a same-key request with an incompatible mode is an explicit
HTTP 409 — never a silent reuse of the wrong result. The ledger records each call attempt, proving
"one external operation, many call attempts". Modes: `success` (valid 200), `timeout` (record
receipt FIRST, then delay past the client timeout on the first call; a later same-key call
reconciles immediately), `invalid_response` (HTTP 200 with a contract-violating body). It is not a
real model Provider and proves nothing about real cost, rate limits or production behaviour.

---

## 8. Common Misconceptions

```text
Timeout
❌ A timeout means the Provider did not execute, so retry.
✅ Receipt/execution is UNKNOWN; with a durable marker go to pending_reconciliation, never blind-retry.

invalid_response
❌ invalid_response is a final Job status.
✅ It is an outcome/reason: HTTP 200 + invalid body is an explicit Provider CONTRACT FAILURE (durable failed facts).

provider_request_id in telemetry
❌ Log the full provider_request_id everywhere for correlation.
✅ It is sensitive/capability-bearing; hash it in telemetry, keep the full value only in PostgreSQL.

Upload success
❌ Upload returned 200, so the Artifact is done.
✅ Verify by HEAD (existence + checksum + size + content type); mismatch = conflict, never overwrite.

Completion authority
❌ Object exists / HTTP 200 / Celery ACK / a trace = success.
✅ Success = ONE guarded PostgreSQL tx under the CURRENT lease_token; a stale Worker updates zero rows.

OTel
❌ If the Collector/exporter fails, fail the Job.
✅ Telemetry is diagnostic, not transactional; a committed Job stays committed; record the limitation.
```

---

## 9. Engineering Trade-offs

```text
Pre-call marker + post-call request id vs "just call and retry on error"
  + Recoverable, no duplicate billable calls; timeout has a safe branch.
  - Two extra durable writes and a reconciliation path to maintain.

Per-Attempt key + HEAD verify vs per-Job key + trust upload 200
  + Idempotent resume, no cross-Attempt overwrite, real integrity check.
  - Extra HEAD round trip and deterministic key discipline.

Object Storage for bytes + PostgreSQL for reference vs result bytes in PostgreSQL
  + Cheap, scalable bytes; DB stays the small durable truth.
  - Two stores to reconcile (orphan objects, forward repair).

OTel correlation vs telemetry-as-truth
  + Diagnosis + correlation without coupling business commit to an exporter.
  - Evidence packs must be reconstructable from durable stores, not traces.
```

---

## 10. Hands-on Exercises

Question: Classify `timeout`, `200 + invalid_response`, and a valid response.

Expected Output: timeout+marker -> `pending_reconciliation` (no blind call); 200+invalid ->
contract failure (durable failed facts); valid -> Artifact HEAD verify -> guarded completion.

---

Question: Design the pre-call and post-call Provider checkpoints.

Expected Output: persist `provider_dispatch_started_at` before the HTTP call; persist
`provider_request_id` as soon as returned and before the Artifact/success path (if it can't
persist, reconcile, do not continue).

---

Question: Can an Artifact object be overwritten after a checksum mismatch? HEAD vs GET?

Expected Output: no — CONFLICT: preserve evidence, reconcile. HEAD is a metadata-only read for
existence/checksum/size/content-type; GET fetches bytes.

---

Question: Reconstruct evidence after an OTel export failure.

Expected Output: from PostgreSQL (Job/Attempt/Event/Artifact/lease), Object Storage (object +
HEAD), and the Provider ledger — telemetry is not required for business truth.

---

Question: Resolve timeout + Worker-loss + expired lease + marker but no `provider_request_id`/
artifact.

Expected Output: freeze the Job, `pending_reconciliation`, query the Provider by the stable key
and check the deterministic Artifact key. If the Provider confirms non-receipt and
deadline/budget/reservation are valid: guarded `pending_reconciliation -> queued`, append Event,
create ONE new durable `job.redispatch_requested` Outbox intent, let the Relay publish (never
`.delay()` as recovery authority). If the deadline expired, a renewed user request needs a NEW
Job. If the Provider confirms completion but the Artifact is missing, retrieve the existing
result first — do not submit a second Provider operation.

---

## 11. Relevant Framework Connections

* **FastAPI:** acceptance persists trace context/business correlation into durable Job + Outbox
  facts and ENDS before background external work.
* **PostgreSQL:** guarded state transitions, lease-token fencing, Job/Attempt/Event/Outbox facts
  and Artifact references.
* **Redis/Celery:** delivery/transport; redelivery/ACK does not confer completion authority.
* **S3-compatible Object Storage / MinIO:** owns bytes + HEAD/metadata verification.
* **OpenTelemetry Collector/exporter:** receives diagnostic signals; NOT a transactional
  prerequisite.

---

## 12. AI Backend Connections

Long-running, billable AI Provider operations may time out after being accepted. The system must
prevent duplicate model calls, preserve recoverable external-operation identities, store
validated generated output as verifiable object artifacts, and retain auditable correlation
under Worker loss. The separate deterministic fake Provider proves adapter HTTP integration
only; it does not prove a real model's cost, rate limits, quality or production reliability.

---

## 13. English Interview

### Key Vocabulary

```text
provider_dispatch_started_at (pre-call marker) · provider_request_id (post-call identity)
correlation/idempotency key · per-Attempt Artifact key · HEAD vs GET · checksum/metadata conflict
guarded completion · lease_token fencing · pending_reconciliation · trace_id/span_id/Span Link
low-cardinality metrics · exporter-failure tolerance
```

### Beginner Question

Q: Why isn't an HTTP 200 from the Provider enough to mark a Job succeeded?

Strong Answer: "A 200 only says the HTTP call returned; it doesn't prove we have a verified
result or the authority to commit. Success is one guarded PostgreSQL transaction under the
current lease token that records a HEAD-verified Result Artifact reference, finishes the
Attempt, writes a success Event, moves the Job to succeeded, and clears the lease. Object
existence, ACK and traces are not business truth."

### Intermediate Question

Q: The Provider call times out. What do you do, and why not retry immediately?

Strong Answer: "A timeout doesn't prove non-execution — the Provider may have received and run a
billable operation. Because we persisted `provider_dispatch_started_at` before the call, the
Job goes to `pending_reconciliation`; we never blind-retry. We reconcile by asking the Provider
with our stable correlation key and by checking the deterministic Artifact key. Only after
confirmed non-receipt (with a valid deadline/budget) do we guardedly requeue with a new durable
`job.redispatch_requested` Outbox intent."

### Senior Question

Q: The upload timed out but a HEAD finds a matching object; later a DB transaction fails after
another upload; and your OTel exporter is down. Walk me through it.

Strong Answer: "Upload-timeout-then-matching-HEAD is not a failure: I forward-repair the Artifact
reference against the existing object and complete under the lease token — no overwrite. A DB
rollback after an upload doesn't undo Object Storage, so I retain and validate the candidate
object, then reconcile or forward-repair, or schedule auditable orphan GC — never a blind
exception-path delete, and never overwrite on a checksum mismatch. The exporter being down is
irrelevant to business truth: the guarded commit still holds, I emit exporter health metrics and
note the telemetry limitation, and I rebuild the evidence pack from PostgreSQL, MinIO and the
Provider ledger."

### Common Weak Answer

"The object is in the bucket and the Provider returned 200, so mark it succeeded." This confuses
storage/HTTP with business truth and skips lease-guarded completion and HEAD verification.

---

### Advanced Question

Q: How do you guarantee a Job can never be marked succeeded without a Provider call and a
verified Artifact — even under retries and a superseded lease?

Strong Answer: "The production Celery task runs one composition: guarded `queued->running`
claim (writing the lease triple), then `run_external_operation` under THAT lease token. Success
is emitted only by the guarded completion inside that function, after a real Provider HTTP call,
an Object Storage PUT and a HEAD verification of checksum/size/content-type on the per-Attempt
key. The composition returns that function's outcome verbatim — it never adds an outer success
or overwrites a transition. tenant and the correlation key come from durable PostgreSQL facts,
not the Celery message. If the lease was superseded after the HTTP response, the guarded UPDATE
matches zero rows and we return `lease_lost_no_commit` instead of a fabricated
pending_reconciliation/failed, so a stale Worker never touches the successor's Job. The old
Day60 skeleton that 'succeeded' without a Provider is a teaching artifact, not the task."

## 14. Mental Model Summary

```text
timeout            = receipt/execution UNKNOWN; marker -> pending_reconciliation; never blind retry
dispatch marker    = pre-call durable checkpoint (not success)
provider_request_id= post-call durable external-operation identity (persist before success path)
correlation key    = ours, pre-call, reused for same-Attempt retries (distinct from provider_request_id)
Artifact key       = deterministic per-Attempt; HEAD-verify existence/checksum/size/content-type
overwrite          = never on mismatch (CONFLICT -> reconcile); forward-repair on timeout+matching HEAD
success            = ONE guarded PostgreSQL tx under the CURRENT lease_token; stale Worker updates 0 rows
OTel               = diagnostic correlation, low-cardinality metrics, exporter failure tolerant
outcomes           = timeout+marker->pending_reconciliation · 200+invalid->contract failure · valid->verify->complete
evidence tiers     = CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION
```

### Mental Model Evolution

```text
Start:  "A timeout means it didn't run — retry."
        "HTTP 200 / object exists = success."
        "Log the full provider_request_id for correlation."
        "One key per Job is fine."
   |
   v
End:    A timeout is UNKNOWN; a durable marker forces pending_reconciliation, never a blind billable retry.
        Success is a lease-guarded PostgreSQL commit with a HEAD-verified Artifact — not HTTP/storage/ACK/trace.
        provider_request_id is protected in PostgreSQL; telemetry uses a hash + low-cardinality labels.
        Keys are per-Attempt; HEAD verifies; conflicts reconcile; OTel is diagnosis, not truth.
```

Assistant-assisted final Chinese mental model (confirmed by the student):

```text
Day61 的核心：外部 Provider 调用超时 ≠ 没执行。调用前先持久化 provider_dispatch_started_at（前置标记，不代表成功），
拿到响应后立刻持久化 provider_request_id（外部操作身份），再走 Artifact/成功路径；若 request_id 持久化失败，
就不能继续成功路径，要保守 reconcile。我们的 correlation/idempotency key 是调用前自己生成、同一 Attempt 重试复用，
与 Provider 返回的 provider_request_id 不同但互补。Result Artifact key 按 Attempt 确定
（results/{tenant}/{job}/{attempt}/result.json），用 HEAD（只读元数据，不是 GET 取字节）校验存在/checksum/size/content-type；
校验不一致就冲突，绝不覆盖，进入 reconciliation；上传超时但 HEAD 命中一致就 forward-repair 引用、不覆盖。
最终成功只有一次：在当前匹配 lease_token 下的一个 PostgreSQL 保护事务（Artifact 引用 + Attempt 完成 + 成功 Event +
Job running->succeeded + 清 lease）；对象存在、HTTP 200、Celery ACK、trace 都不是成功，过期 token 的旧 Worker 改 0 行。
OTel 只是诊断关联，不是业务真相：低基数标签、不无条件记录完整 provider_request_id（用哈希），Collector/exporter 挂了
也不能回滚已提交的 Job 或触发第二次 Provider 调用。分类：超时+标记 -> pending_reconciliation；200+非法 body -> 契约失败；
合法 -> 校验 Artifact -> 保护完成。
```

---

## 15. Today's Takeaway

* Most important mental model: a timeout is UNKNOWN; with a durable marker the Job goes to
  `pending_reconciliation`, never a blind billable retry.
* Most important production risk: treating HTTP 200 / object existence / ACK / a trace as
  success, or overwriting on a checksum conflict.
* Most important framework/AI connection: PostgreSQL owns the protected `provider_request_id`
  and lease-guarded completion; Object Storage owns HEAD-verified bytes; OTel is diagnosis.
* Most important interview answer: success is one guarded transaction under the current
  `lease_token`, not any external signal.

---

## 16. Before Next Lesson Checklist

```markdown
- [ ] Can I explain why a Provider timeout is not proof of non-execution?
- [ ] Can I place the pre-call marker and post-call provider_request_id correctly, and say why order matters?
- [ ] Can I distinguish our correlation key from provider_request_id?
- [ ] Can I design a per-Attempt Artifact key and verify it by HEAD, with non-overwrite conflict behaviour?
- [ ] Can I state the guarded completion condition under the current lease_token?
- [ ] Can I explain why OTel is not business truth and how exporter failure is tolerated?
- [ ] Can I classify timeout / invalid-200 / valid and state Day61's evidence tiers and NOT RUN limits?
```

---

Related: [Day61 design & runbook](../../projects/ai-backend-data-layer/api/day61-object-storage-provider-adapter-and-opentelemetry-end-to-end-evidence-design.md) ·
[Day60 lesson](day60-outbox-redis-celery-broker-and-worker-recovery-integration.md) ·
[FastAPI cheat sheet](../../cheat_sheets/fastapi.md) ·
[FastAPI interview](../../interview/fastapi.md)
