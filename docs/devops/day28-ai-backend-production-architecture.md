# Lesson 28 — AI Backend Production Architecture

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day27 — Kubernetes Workloads

Previous Lesson: [Day27 — Kubernetes Workloads](day27-kubernetes-workloads.md)

Next Lesson: Day29 — PostgreSQL Foundations and Durable Relational State (Phase 3 — Backend Foundations; planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day29 lesson file does not exist yet)

Engineering Artifact: A conceptual Production AI Backend Architecture Blueprint (`examples/ai-backend-architecture/`) — responsibility map, request/upload/job flows, state machines, a state/data ownership table, the outbox/idempotency boundaries, a failure/rollback/data-repair matrix, monitoring/observability signals, and an explicit validation-limitations section — see [examples/ai-backend-architecture/README.md](../../examples/ai-backend-architecture/README.md).

DevOps Cheat Sheet: [cheat_sheets/devops.md](../../cheat_sheets/devops.md)

DevOps Interview: [interview/devops.md](../../interview/devops.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 90-120 minutes
Blueprint authoring / static review: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

This is the Phase 2 closing lesson. It shifts the student from "I can deploy components" to "I can
define component responsibility, lifecycle, state/data ownership, failure boundaries, recovery
policy, and the evidence needed to operate the whole system."

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Separate the FastAPI HTTP request lifecycle from a long-running Celery job lifecycle and return `202 + job_id` quickly.
* Assign every job state to its owner: PostgreSQL owns durable truth, Redis delivers/accelerates, Object Storage owns large bytes, process memory is request-local.
* Explain the database→queue crash gap and derive the Transactional Outbox with at-least-once delivery + idempotent processing.
* Design durable checkpoints, atomic claim/lease, and a stable idempotency key enforced by a unique constraint/upsert.
* Choose Object Storage for large files and design presigned direct multipart upload with an Upload Session and server-side verification.
* Design provider retry with exponential backoff + jitter, max attempts/deadline, error classification, and a global circuit breaker.
* Choose monitoring signals (queue depth vs oldest-age vs throughput) and observability correlation identity (stable `job_id`, not `job_status`).
* Order a failure-containment/rollback/data-repair runbook and explain why compute rollback does not repair persisted data.
* Answer beginner, intermediate, and senior production-architecture interview questions in English.

The engineering artifact is a conceptual architecture blueprint, not a runnable service.

---

# Why This Matters

A user uploads a 500 MB document to a RAG platform through `POST /documents`. Parsing, chunking,
embedding, and indexing take about eight minutes. The naive design does all of this inside the
FastAPI HTTP request, which causes:

```text
Ingress timeout -> client retry -> duplicate model cost -> unclear progress
-> lost in-memory state when an API Pod is replaced
```

Why a backend engineer must care:

```text
Responsibility -> each component has ONE clear responsibility in the Job lifecycle.
State ownership -> an accepted job is a durable business commitment, not memory or a broker message.
Delivery       -> at-least-once + idempotent effects, because exactly-once across systems is a myth.
Large data     -> big bytes live in Object Storage; the DB keeps metadata/pointers.
Recovery       -> retries are bounded, classified policy — not an infinite loop.
Evidence       -> monitoring detects known-abnormal; observability explains WHY it failed.
Repair         -> compute rollback stops future damage; data repair fixes what is already persisted.
```

Day28 is where all Phase 2 primitives become one operable system with clear boundaries and evidence.

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day25-27)
        |
        v
Current Concept (Day28: production AI Backend — responsibilities, state/data ownership, async jobs,
                 failure recovery, monitoring, observability)
        |
        v
Future Deepening (Phase 3 Backend Foundations: PostgreSQL, SQL, Redis, Database Design)
```

Where Day28 sits:

```text
Safe deployment (Day25) -> Kubernetes foundations (Day26) -> Kubernetes workloads (Day27)
-> Production AI Backend architecture (Day28, Phase 2 close)
-> Phase 3 Backend Foundations (durable data, SQL, Redis, database design)
```

Day27 primitives reused:

```text
- Replaceable compute must not own durable business truth.
- Queue backlog scales the WORKER Deployment that consumes the queue, not the API producer.
- Readiness / HTTP 200 is not proof of business correctness.
- Rolling back desired compute state does not undo external side effects or corrupted data.
- Static rendering/schema checks and runtime/business validation are different evidence levels.
```

Future connection only: Phase 3 deepens the boundaries set here — PostgreSQL as durable truth, SQL
for atomic transitions/constraints, Redis for transient coordination, Database Design for the Job/
Upload-Session/event/document/result/provenance models. The ROADMAP does not assign Day29/Day30
titles, so none are invented here.

---

# Lesson Map

```text
Request vs Job lifecycle (202 + job_id; long work -> worker)
  -> State ownership (PostgreSQL truth / Redis deliver / Object Storage bytes / memory transient)
  -> DB->Queue consistency (crash gap -> Transactional Outbox -> at-least-once + idempotent)
  -> Durable checkpoints, leases, idempotency keys (unique constraint / upsert; ACK after durable)
  -> Object Storage + control-plane/data-plane boundary
  -> Presigned direct multipart upload + Upload Session verification
  -> Retry policy (backoff + jitter + max attempts/deadline + classification + circuit breaker)
  -> Monitoring (depth vs oldest-age vs throughput; thresholds/SLOs)
  -> Observability (stable job_id correlation; low-cardinality metrics; structured logs/traces/events)
  -> Failure containment, rollback, and data repair (contain -> restore -> identify -> rebuild -> verify)
```

---

# Core Mental Model

```text
FastAPI accepts and exposes (control plane; returns 202 + job_id).
Celery executes (worker tasks, outside the HTTP connection and API Pod lifetime).
Queue / Redis transports and coordinates (delivery + optional cache), NOT durable truth.
PostgreSQL owns durable truth (Job lifecycle, metadata, outbox, events, checkpoints, provenance).
Object Storage owns large bytes (immutable originals + derived artifacts).
Monitoring detects known abnormal signals against thresholds/SLOs.
Observability explains internal behavior via metrics + structured logs + traces + durable events.
At-least-once delivery requires idempotent effects.
Compute rollback does not repair data.
```

Central boundary:

```text
HTTP Request Lifecycle != Long-running Job Lifecycle
PostgreSQL owns the Job. Redis delivers or accelerates. FastAPI exposes. Celery executes.
```

---

# Main Concepts

## Concept 1: FastAPI Request Lifecycle vs Long-running Job Lifecycle

Tech Lead Question:

An eight-minute pipeline runs inside `POST /documents`. Where should the processing actually happen,
and what should the API return?

Student Thinking:

Holding the HTTP connection for eight minutes blocks the request and risks timeouts.

Student Answer:

> "尽快返回一个job_id,并把处理交给后台。最重要的生产原因是不耽误其他的job继续请求"

Tech Lead Review:

Correct. FastAPI should authenticate, validate, establish the durable job commitment, return quickly
with `202 Accepted` + a stable `job_id`, and expose status/result APIs. Long processing belongs to a
Celery worker, outside the HTTP connection and the API Pod lifetime.

```text
HTTP Request Lifecycle != Long-running Job Lifecycle
```

A long-running `async def` inside FastAPI is NOT a durable job system: by itself it gives no durable
acceptance, redelivery, retry policy, progress recovery, or survival across Pod restart. Celery
workers execute tasks; the Queue transports/delivers task messages. Redis/the Queue is not the
durable owner of the Job.

Conceptual flow:

```text
Client -> FastAPI -> PostgreSQL Job + Outbox -> Queue/Redis broker -> Celery Worker
Client <- 202 {job_id}                          Worker -> durable checkpoints/results
Client -> GET /jobs/{job_id} -> PostgreSQL-backed status/result reference
```

Engineering Thinking:

The request accepts and commits; the worker executes. Separate the two lifecycles so the job survives
disconnects and Pod replacement.

Production Example:

`POST /documents` returns `202 {job_id}` in milliseconds; a worker embeds for eight minutes; the
client polls `GET /jobs/{job_id}`.

Framework Connection:

Day27 gave separate API and worker Deployments; this is why they are separate — different lifecycles.

Exercise:

Decide whether an eight-minute pipeline belongs in the FastAPI request or a worker, and justify it.

## Concept 2: State Ownership — PostgreSQL vs Redis vs Process Memory

Tech Lead Question:

The API returned `202 + job_id`. Where does each job state (queued/running/succeeded/failed) live?

Student Thinking:

Queued jobs feel like Redis/Celery; final results feel like PostgreSQL; transient stuff can stay in
memory.

Student Answer:

> "FastAPI 内存因为现在是一个临时状态，redis主要是queue job，postgresql存放最终状态与结果数据"

Tech Lead Review:

The instinct is common but the boundary is wrong. Once you return `202`, the Job is a durable business
commitment — it cannot live only in FastAPI memory or only in the broker.

```text
PostgreSQL owns the Job source of truth for EVERY lifecycle state, not merely the final result:
queued, running, retry_wait, succeeded, failed_terminal, invalidated, reprocessing.
```

PostgreSQL also owns durable metadata: document/object reference, checksum/version, owner, attempt
count, current stage, timestamps, error info, result reference, and provenance. Redis may be Celery's
broker and may cache high-frequency progress, but broker/cache state is transient coordination, not
authoritative business state. FastAPI process memory is request-local only.

```text
PostgreSQL owns the Job. Redis delivers or accelerates. FastAPI exposes. Celery executes.
```

Don't write a database row per tiny chunk just to show a percentage: keep coarse durable stage/
checkpoint state in PostgreSQL and use a cache for high-frequency UI progress when justified.

Engineering Thinking:

Durable business truth belongs in the one component whose job is durability. Everything replaceable
(memory, broker, cache) must be reconstructable from it.

Production Example:

After an API Pod restart, the job's real state is read from PostgreSQL — not from memory or the
broker.

Framework Connection:

Day26/27: replaceable Pods must not own durable truth; PostgreSQL (StatefulSet/managed) does.

Exercise:

Assign queued/running/succeeded/failed to memory, Redis, or PostgreSQL and defend it.

## Concept 3: Database→Queue Consistency and the Transactional Outbox

Tech Lead Question:

Do you write PostgreSQL first or publish to the queue first? What can still go wrong?

Student Thinking:

Persist state first so a crash is recoverable from the durable record.

Student Answer:

> "我会先写postgresql，再投递queue，先讲现在状态写入持久化数据，之后就算崩溃，也可以通过状态进行判断是重启job还是继续进行 job避免重复执行。"

Tech Lead Review:

Right direction — durable business state must precede reliance on delivery. But a naive "insert Job,
then publish" still has a crash gap:

```text
INSERT Job (QUEUED) -> [crash] -> no task message ever published
=> PostgreSQL says QUEUED while no worker will ever pick it up.
```

Two mitigations:

```text
- Reconciliation scanner: periodically find stale QUEUED jobs and republish them.
- Transactional Outbox (stronger): in ONE PostgreSQL transaction, insert the Job AND an Outbox event.
  A relay publishes unsent events to the Queue and marks them sent.
```

Honest limit: the Outbox makes business state + intent-to-publish atomic; it does NOT create
exactly-once delivery. If the relay publishes and crashes before marking the event sent, it republishes.

```text
Production model = at-least-once delivery + idempotent processing.
```

Engineering Thinking:

You cannot atomically write two independent systems (DB and broker). Make the write atomic within the
DB (Outbox), then tolerate duplicate delivery with idempotency.

Production Example:

A relay reads `outbox WHERE sent_at IS NULL`, publishes, marks sent; a duplicate publish after a relay
crash is absorbed by the idempotent worker.

Framework Connection:

Redis/Celery is the transport; PostgreSQL is the truth + the outbox.

Exercise:

Choose DB-first vs Queue-first, analyze the crash windows, and derive the Transactional Outbox.

## Concept 4: Durable Checkpoints, Leases, and Idempotency

Tech Lead Question:

A worker crashes after writing an embedding but before ACK. How do you avoid repeating completed work
and avoid two workers doing the same job?

Student Thinking:

Track finer-grained progress so you know where to resume.

Student Answer:

> "不够，检查job的status只能粗粒度的查看状态，应该查work的进度状态，并对几个重要步骤做颗粒度进度划分，比如调用模型、生成并写入 Embedding分别对应进度"

Tech Lead Review:

Good — coarse status is not enough. But a progress percentage is a UX signal, not a safe recovery
checkpoint, and progress is not mutual exclusion. Full model:

```text
Durable stages:  UPLOADED -> PARSED -> CHUNKED -> EMBEDDING -> INDEXED -> SUCCEEDED
Atomic claim:    a worker claims work with an owner/lease; an expired lease permits recovery.
Idempotency key: stable identity, e.g. (document_id, chunk_hash, model_version).
Enforcement:     a DB unique constraint + idempotent upsert; check durable state before repeating.
ACK timing:      ACK the queue ONLY after the result and checkpoint are durably recorded.
```

External calls are the hard part: if a provider call succeeds but the local checkpoint write fails, a
redelivery may repeat the external call (and cost). Use a provider idempotency key if available. For a
separate vector store (no shared transaction with PostgreSQL), use stable vector IDs/idempotent upsert,
versioned indexes, and reconciliation. Do not claim strict exactly-once when external systems cannot
join one transaction.

Memory aid:

```text
Progress percentage = user experience.
Durable checkpoint  = recovery location.
Idempotency key + uniqueness = duplicate side-effect control.
Lease = exclusive attempt ownership with expiry.
```

Engineering Thinking:

Make each step resumable and each effect idempotent; ACK last. Correctness comes from durable state +
uniqueness, not from hoping a message is delivered once.

Production Example:

A redelivered task sees `INDEXED` already recorded for `(doc, chunk_hash, model_v)` and skips the
model call and write.

Framework Connection:

pgvector/vector index gets stable IDs + versioned namespaces; PostgreSQL enforces the unique key.

Exercise:

Recover from a worker crash after the embedding write but before ACK; derive checkpoints, leases, and
idempotent writes.

## Concept 5: Object Storage and the Control-plane/Data-plane Boundary

Tech Lead Question:

Where does the 500 MB source document (and large generated artifacts) live — Pod disk, Redis,
PostgreSQL, or Object Storage?

Student Thinking:

Pod disk fills up and isn't shared; big blobs shouldn't sit in Redis or the DB.

Student Answer:

> "我会选择Object Storage，因为pod本地最好运行应用，pod分配的存储空间会被迅速塞满，影响运行效率。redis最好存放queue job，postgresql存放状态、文件地址等，把大文件放在Object Storage方便扩容"

Tech Lead Review:

Correct choice. Narrow the reason: the stronger production issue is that replaceable Pod-local storage
has the wrong lifetime and is not shared across workers — capacity pressure is secondary.

```text
Pod-local disk -> replaceable, unshared (wrong lifetime/ownership).
Redis          -> memory-oriented; capacity/eviction/cost trade-offs.
PostgreSQL     -> large blobs bloat DB I/O, backups, replication.
Object Storage -> large immutable/derived bytes; scalable, shared, durable.
```

Split of ownership:

```text
PostgreSQL     -> metadata, ownership, checksum/object version, status, object/result references.
Object Storage -> the large bytes themselves.
```

Security: an object key is not authorization. Use tenant isolation, server-controlled keys, short-lived
scoped signed operations, checksum verification, and never log signed URLs or credentials.

Engineering Thinking:

Separate the control plane (who/what/verify, in the DB) from the data plane (the bytes, in Object
Storage). Keep each in the component with the right lifetime.

Production Example:

The DB row holds `object_key`, `checksum`, `version`, `owner`; the 500 MB bytes and the derived index
artifacts live in Object Storage.

Framework Connection:

RAG originals are immutable durable inputs; embeddings/indexes are derived, rebuildable outputs.

Exercise:

Select storage for a 500 MB source file and explain the Pod/Redis/PostgreSQL/Object Storage trade-offs.

## Concept 6: Direct Multipart Upload and the Upload Session Lifecycle

Tech Lead Question:

Should the 500 MB upload stream through FastAPI, and when do you create the Job?

Student Thinking:

Routing 500 MB through the Pod adds load and risks mid-transfer failure; create the Job only after the
object really exists.

Student Answers:

> "我觉得应该由 FastAPI 生成一个短时上传地址，让客户端直接上传到 Object Storage，因为大文件经过pod，增加存储压力，而且可能会因为网络问题导致传输中断。"

> "等客户端报告上传完成、FastAPI 验证对象确实存在后，再创建 Job 并投递。有完整的对象调用大模型进行处理的时候才有具体的文件，签发上传地址就创建有可能文件在上传过程中中断或者文件不完整。work已经在执行大模型调用了"

Tech Lead Review:

Correct on both counts, with reinforcement. FastAPI is the control plane: authenticate, authorize,
create a durable Upload Session, choose a server-controlled object key, and issue a short-lived
presigned upload URL. The client uploads directly to Object Storage (preferably multipart). FastAPI
should not proxy the whole byte stream unless product/security demands it.

Direct upload removes the 500 MB from the API path but does NOT remove network failure — multipart
upload, retry, and cleanup are still needed. The client completion call is an untrusted trigger:

```text
Verify BEFORE creating the Job: object existence, size, checksum/version, ownership, required scan.
Only THEN, in ONE PostgreSQL transaction, create the Job + Outbox event.
Bind the Job to an immutable object version/checksum (avoid overwrite / TOCTOU).
```

Two separate state machines:

```text
Upload Session: INITIATED -> UPLOADING -> VERIFIED | FAILED | EXPIRED
Job:            QUEUED -> RUNNING -> RETRY_WAIT -> ... -> SUCCEEDED | FAILED_TERMINAL
```

Create the Upload Session when the URL is issued so ownership, limits, audit, expiration, orphan-upload
cleanup, and abandoned-multipart cleanup stay visible.

Engineering Thinking:

Trust the server's verification, not the client's "done." Keep upload and job as distinct lifecycles.

Production Example:

A client that never completes leaves an `EXPIRED` Upload Session and an orphan multipart to clean up —
no Job was created.

Framework Connection:

FastAPI issues scoped credentials; Object Storage holds the bytes; PostgreSQL records the session/job.

Exercise:

Choose API-proxied vs presigned direct upload, and separate the Upload Session lifecycle from the Job
lifecycle.

## Concept 7: Retry Policy, Backoff, Jitter, and Provider Protection

Tech Lead Question:

A provider returns 429/503/timeouts, and there's a 20-minute outage. What is a complete retry policy?

Student Thinking:

Wait and grow the delay exponentially, with a cap.

Student Answer:

> "应该设置时间等待机制，等待时间指数级增加，设置一个最大等待时间"

Tech Lead Review:

Good foundation, but a max delay alone can still allow infinite attempts. Complete policy:

```text
- Exponential backoff + JITTER (avoid synchronized retry storms).
- Bound by MAX ATTEMPTS and/or an overall RETRY DEADLINE (not just a max delay).
- Classify failures instead of retrying everything:
  429              -> honor Retry-After; rate-limit/back off with jitter.
  503 / timeouts   -> retry within policy.
  400 / parse      -> terminal, no retry.
  401/403/config   -> stop or contain globally and alert; do not let 1,000 jobs create retry storms.
- Global rate limiter / circuit breaker when the upstream is degraded.
- Persist attempt_count, next_retry_at, last_error, retry_deadline, provider_request_id.
```

```text
Retry is a controlled recovery policy, not an automatic infinite loop.
```

Engineering Thinking:

Retries protect the provider and your cost as much as the job. Classification + global breakers stop a
single outage from becoming a self-inflicted DDoS.

Production Example:

During the 20-minute outage a circuit breaker opens, jobs move to `RETRY_WAIT` with jittered
`next_retry_at`, and terminal `401`s alert instead of retrying 1,000 times.

Framework Connection:

Day27 HPA could scale workers, but more workers against a degraded provider just multiplies 429s/cost —
retry policy + breaker matter more than replicas.

Exercise:

Design provider retry behavior for 429/503 and a 20-minute outage.

## Concept 8: Monitoring — Known Signals, Thresholds, and SLO Evidence

Tech Lead Question:

Queue depth is high. Is the system failing? What single signal is closest to the user's pain?

Student Thinking:

Depth can be high just from load; the oldest waiting job is closer to real trouble.

Student Answer:

> "还是最老任务已经等待了多长时间，因为queue中任务总数量大可能会因为网络延迟、请求量大等因素导致job堆积，并不代表没有正常推进任务。而最老任务等待过长时间，大概率是任务出问题了"

Tech Lead Review:

Right: oldest queued-job age is usually closer to user waiting/SLO than depth. But oldest age alone is
a symptom, not a root cause. Combine signals:

```text
depth rising + age rising + throughput ~0     -> likely failure/stall.
depth rising + age rising + throughput normal -> progressing but under capacity.
depth high  + age low                          -> likely a recent burst.
```

Signal catalog:

```text
API:      request rate, error rate, latency.
Queue:    depth, oldest age, enqueue/dequeue rate.
Worker:   active workers, task duration, completion throughput, retry rate, terminal failures.
Provider: latency, 429/503, cost.
Business: end-to-end Job latency, success rate, stuck jobs by stage.
```

Monitoring evaluates known metrics against thresholds/SLOs and drives alerts. Alert sensitivity trades
early detection against false positives and alert fatigue.

Engineering Thinking:

No single number is the truth; correlate inventory (depth), user pain (oldest age), and progress
(throughput) before paging.

Production Example:

Depth 5,000 + oldest age 2 min + high throughput = a burst draining; depth 300 + oldest age 40 min +
zero throughput = a stall to page on.

Framework Connection:

The worker HPA's primary scaling signal is still queue backlog (ideally backlog per worker, or an
equivalent work-pressure metric). Oldest queued-job age is closer to user waiting/SLO and is best used
for alerting and diagnosis; throughput shows whether the queue is still progressing or is under
capacity. A single stuck or poison-pill job can keep oldest age rising, so it must not be used
unqualified as a scale-up trigger. Scaling remains bounded by provider rate limits, cost, and
maxReplicas.

Exercise:

Compare queue depth with oldest Job age and use throughput to interpret the signal.

## Concept 9: Observability and Cross-component Correlation

Tech Lead Question:

Which identifier ties a request across FastAPI, the queue, Celery attempts, PostgreSQL, and provider
logs?

Student Thinking:

Something that stays constant through the whole path.

Student Answers:

> "应该携带job status"  (first attempt)

> "job_id、job_status保持不变，task_id/attempt_id变化。因为job_id是 Job 的稳定身份保持不变，重试三次说明没有正常运行，所以status都是相同。task_id/attempt_id是每个job的每次重试"

Tech Lead Review:

`job_status` is a changing value shared by many jobs — it cannot correlate. And status does NOT stay
constant: it evolves. Identity model:

```text
job_id              -> STABLE across request, queue, attempts, logs, traces, durable events.
trace_id            -> follows a distributed request/path.
attempt_id/count    -> distinguishes execution attempts (application-owned).
broker task_id      -> delivery/implementation id; may or may not change on retry — don't rely on it.
provider_request_id -> links an external call to provider-side evidence.
```

Structured logs carry service, job_id, trace_id, task_id, attempt_id/count, stage, state, duration,
safe error code. Do NOT use `job_id` as a normal metric label (high cardinality) — per-job identity
belongs in logs/traces; keep metric labels low-cardinality. Never log document content, presigned URLs,
keys, tokens, passwords, or unnecessary personal data.

```text
Identity remains stable. State evolves. Attempts distinguish executions. Events preserve history.
```

Durable history:

```text
jobs.current_status      -> current projection.
append-only job_events   -> transitions, attempts, failures, invalidation, recovery history.
```

Monitoring tells whether known signals are abnormal; Observability combines metrics + structured logs +
traces + durable business events/state to explain internal behavior and WHY it failed.

Engineering Thinking:

Correlate on stable identity, preserve history append-only, and keep metrics low-cardinality.

Production Example:

An incident is reconstructed by filtering all logs/traces/events on one `job_id` across every component.

Framework Connection:

`provider_request_id` connects your logs to the provider's dashboard for a disputed/expensive call.

Exercise:

Select correlation identifiers across FastAPI, Queue, Celery, PostgreSQL, provider, and logs/traces.

## Concept 10: Production Failure Containment, Rollback, and Data Repair

Tech Lead Question:

Worker release v2 passes readiness but uses the WRONG embedding model. It writes wrong embeddings/index
entries for 100 Jobs before anyone notices. Is rolling back to v1 enough?

Student Thinking:

Rollback stops new damage, but the 100 bad results are already persisted.

Student Answers:

> "不够，因为100个job的最终state都保存在postgresql,其中包含了错误Embedding的索引。需要进行清理"

> "A B C D E ,如果不暂停，会有新的错误的job被执行"

Tech Lead Review:

Correct. Compute rollback stops future bad compute; it does not repair persisted state, object
artifacts, vector/index entries, or external side effects.

```text
Preserve provenance: job_id, worker_release, processing_version, embedding_model/version,
                     index namespace/version, source checksum, completed_at.
Identify the affected set precisely from provenance + time/release boundaries (no blind deletes).
Lifecycle: SUCCEEDED -> INVALIDATED -> REPROCESSING -> SUCCEEDED (preserve event history).
Prefer versioned derived indexes: build/validate a clean version, then switch an alias/current pointer.
Immutable originals in Object Storage are durable source inputs; embeddings/indexes are derived/rebuildable.
```

Ordered runbook:

```text
A. Pause/contain bad v2 workers first (no new wrong results).
B. Restore the known-good v1 desired release; verify model/config + readiness.
C. Use provenance to identify and quarantine/invalidate affected results so they are not served.
D. Idempotently reprocess from immutable originals into a clean/versioned index.
E. Verify counts, model/version/dimensions, real RAG output quality, errors, latency, cost, and Job
   success; then switch the index alias/current pointer and restore normal processing.
```

```text
Compute rollback stops future damage. Data repair corrects damage already persisted.
```

Engineering Thinking:

Contain first, restore compute, then repair data by provenance — never delete broadly, and re-expose
only after verification via an alias switch.

Production Example:

A clean index `v2026-07-18b` is built from originals and validated; the `current` alias flips only after
RAG quality checks pass.

Framework Connection:

Day27 rollback restored compute; Day28 adds the data-repair half that rollback cannot do.

Exercise:

Order the production failure/rollback/data-repair runbook for a wrong embedding model.

---

# Common Misconceptions

## Mental Model Evolution (Day27 -> Day28)

```text
Initial: "I can deploy the components (API, worker, Redis, PostgreSQL, Object Storage), so the system
          is production-ready."
Reasoning: Day27 gave routing, scaling, rollout, stateful identity, and Helm packaging.
Correction: Deploying components is not architecture. You must define WHO owns each state and byte, how
            an accepted job survives replacement/retry, which delivery guarantees hold, how failures are
            contained, how data is repaired, and which evidence proves business correctness.
Final: FastAPI accepts/exposes, Celery executes, Queue/Redis transports, PostgreSQL owns durable truth,
       Object Storage owns large bytes; at-least-once needs idempotent effects; monitoring detects and
       observability explains; compute rollback does not repair data.
```

## Misconception list

```text
PostgreSQL only stores final state
❌ Redis holds queued jobs, memory holds transient state, PostgreSQL holds only final results.
✅ After 202, every accepted job state is a durable commitment; PostgreSQL owns the whole lifecycle.
   Redis brokers/caches; memory is request-local.
```

```text
DB-first alone solves DB/Queue consistency
❌ Insert Job then publish, and inspect state after a crash.
✅ A crash between commit and publish leaves QUEUED with no message; use reconciliation and/or a
   Transactional Outbox, and make consumers idempotent (duplicate publish is possible).
```

```text
A progress/stage record prevents duplicate work
❌ Recording finer stages stops two workers repeating work.
✅ Progress is not mutual exclusion; need durable checkpoint + atomic claim/lease + idempotency key +
   unique constraint/upsert. External effects may still need provider idempotency + reconciliation.
```

```text
Pod disk is just a capacity problem
❌ Use Object Storage mainly because Pod disk fills up.
✅ The stronger reason is that replaceable Pod-local storage has the wrong lifetime and is unshared;
   capacity is secondary.
```

```text
Direct upload removes network failure
❌ Presigned direct upload makes transfers reliable.
✅ It removes FastAPI from the byte path but client->storage interruptions still happen; multipart +
   retry + cleanup remain necessary.
```

```text
Client "completed" means the upload is complete
❌ Trust the client's completion callback and create the Job.
✅ The callback is untrusted; verify size, checksum/version, ownership, and policy first, via a durable
   Upload Session, then create the Job.
```

```text
Backoff + max wait is complete retry control
❌ Exponential backoff with a cap is enough.
✅ Also need jitter, max attempts/overall deadline, error classification, Retry-After, and a global
   rate limiter/circuit breaker with provider cost/capacity limits.
```

```text
Oldest queue age identifies the root cause
❌ Oldest age tells you what is broken.
✅ It's a symptom closer to SLO than depth, but combine it with depth, throughput, worker state,
   provider errors, and stage distribution to find the cause.
```

```text
job_status is the cross-component identifier
❌ Correlate components by job_status.
✅ Status changes and is shared by many jobs; correlate on stable job_id (plus trace_id, attempt_id,
   task_id, provider_request_id for their scopes).
```

```text
Job status stays unchanged across retries
❌ Status is constant while attempts change.
✅ job_id is stable; status evolves (QUEUED/RUNNING/RETRY_WAIT -> SUCCEEDED/FAILED_TERMINAL); keep
   transitions in append-only job_events and an application-owned attempt id.
```

```text
Idempotency = read then upsert = no duplicate effect
❌ Query then write prevents all duplicates and gives exactly-once.
✅ A separate read+write can race; enforce a DB unique constraint + atomic upsert. It stops duplicate
   durable writes for that key, not a duplicate external call that already succeeded. Assume
   at-least-once; never promise exactly-once across independent systems.
```

```text
Code rollback is a complete rollback
❌ Rolling back the worker fixes everything.
✅ Compute rollback stops future bad execution; persisted PostgreSQL state, Object Storage artifacts,
   and vector indexes need identification, quarantine, invalidation, reprocessing, verification, and
   controlled re-exposure.
```

---

# Engineering Trade-offs

```text
In-request processing vs async worker
+ In-request: simplest, one round trip.
- In-request: HTTP timeouts, lost state on Pod restart, blocked API capacity.
+ Worker: durable, survivable, scalable.
- Worker: needs a queue, durable state, idempotency, and more moving parts.
```

```text
Reconciliation scanner vs Transactional Outbox
+ Scanner: simple; catches stale QUEUED rows.
- Scanner: latency between crash and recovery.
+ Outbox: atomic business-state + intent; low-latency relay.
- Outbox: a relay to run and monitor; still at-least-once (possible duplicate publish).
```

```text
Coarse durable checkpoints vs per-chunk rows
+ Coarse: cheap, low DB write volume.
- Coarse: less granular resume/progress.
+ Per-chunk: precise resume/progress.
- Per-chunk: high write volume/bloat; use a cache for high-frequency UI progress instead.
```

```text
Presigned direct upload vs API-proxied upload
+ Direct: no 500 MB through the Pod; less API bandwidth/pressure.
- Direct: client-controlled path; needs verification + Upload Session + cleanup.
+ Proxied: full server control of the stream.
- Proxied: API bandwidth/memory pressure and Pod as a data-path bottleneck.
```

```text
Object Storage vs PostgreSQL large objects vs Redis
+ Object Storage: scalable durable large bytes; separate lifetime.
- Object Storage: extra system, signed-access design.
- PostgreSQL blobs: bloat I/O, backups, replication.
- Redis blobs: memory cost/eviction.
```

```text
Aggressive retry vs bounded classified retry
+ Aggressive: fast recovery on transient errors.
- Aggressive: retry storms, provider 429/cost, self-inflicted outage.
+ Bounded+classified+breaker: protects provider and cost.
- Bounded: more policy to design and persist.
```

```text
Sensitive alerts vs tolerant alerts
+ Sensitive: early detection.
- Sensitive: false positives, alert fatigue.
+ Tolerant: fewer pages.
- Tolerant: slower detection. Tie thresholds to SLOs and correlate signals.
```

```text
Low-cardinality metrics vs per-job labels
+ Low-cardinality: scalable metrics backend.
- Low-cardinality: less per-job detail in metrics (put it in logs/traces).
- Per-job labels: cardinality explosion, cost, instability.
```

```text
Compute rollback vs data repair
+ Compute rollback: fast, stops future damage.
- Compute rollback: does not fix persisted data/artifacts/indexes.
+ Data repair (provenance + versioned rebuild + alias switch): corrects persisted damage.
- Data repair: slower, needs provenance and verification.
```

---

# Hands-on Exercises

The engineering artifact is a conceptual blueprint (see `examples/ai-backend-architecture/`).

## Exercise 1: Request vs Worker
Question: Does an eight-minute pipeline belong in the FastAPI request or a worker?
Expected Output: Worker; the API returns `202 + job_id` and exposes status. Separate lifecycles.

## Exercise 2: State Ownership
Question: Assign queued/running/succeeded/failed to memory, Redis, or PostgreSQL.
Expected Output: All durable job states -> PostgreSQL; Redis brokers/caches; memory is request-local.

## Exercise 3: DB→Queue Consistency
Question: DB-first or Queue-first? Analyze the crash window and derive the Outbox.
Expected Output: DB-first; crash between commit and publish -> Outbox in one transaction + relay;
at-least-once + idempotent.

## Exercise 4: Checkpoints and Leases
Question: Recover a worker crash after the embedding write but before ACK.
Expected Output: Durable checkpoint + atomic lease + idempotency key (unique constraint/upsert); ACK
after durable write; provider idempotency for external calls.

## Exercise 5: Storage Choice
Question: Where does a 500 MB source file live?
Expected Output: Object Storage (lifetime/sharing, not just capacity); DB keeps metadata/pointers.

## Exercise 6: Upload Path
Question: API-proxied vs presigned direct upload; design verification/cleanup.
Expected Output: Presigned multipart direct upload; verify existence/size/checksum/ownership; Upload
Session; create Job only after verification.

## Exercise 7: Two State Machines
Question: Separate Upload Session lifecycle from Job lifecycle.
Expected Output: `INITIATED->UPLOADING->VERIFIED|FAILED|EXPIRED` vs `QUEUED->RUNNING->RETRY_WAIT->
SUCCEEDED|FAILED_TERMINAL`.

## Exercise 8: Retry Policy
Question: Design provider retry for 429/503 and a 20-minute outage.
Expected Output: Backoff+jitter, max attempts/deadline, classification, Retry-After, circuit breaker;
persist attempt state.

## Exercise 9: Queue Signals
Question: Compare depth vs oldest age; use throughput to interpret.
Expected Output: Oldest age ~ SLO; combine with depth + throughput (stall vs burst vs under-capacity).

## Exercise 10: Correlation Identity
Question: Pick correlation IDs across FastAPI/Queue/Celery/PostgreSQL/provider/logs.
Expected Output: Stable `job_id` (not `job_status`); trace_id/attempt_id/task_id/provider_request_id by
scope; low-cardinality metrics.

## Exercise 11: Failure Runbook
Question: Order the runbook for a wrong embedding model that passed readiness.
Expected Output: A-contain, B-restore compute, C-identify/quarantine by provenance, D-idempotent
rebuild, E-verify + alias switch.

## Exercise 12: English Interview
Question: Answer Beginner, Intermediate, and Senior questions in English.
Expected Output: See the English Interview section, including at-least-once + idempotency for Senior.

## Exercise 13: Final Mental Model
Question: Produce a Chinese Mental Model across all components.
Expected Output: See Mental Model Summary, with the recorded narrow corrections applied.

---

# Relevant Framework Connections

## FastAPI
Request/control plane: authentication/authorization, presigned URL issuance, upload verification,
durable Job creation, the `202` response, and status/result APIs. It accepts and exposes; it does not
execute long jobs.

## Celery
Worker task execution, retry/ACK behavior, task/attempt context. It executes; it is NOT the Job source
of truth. ACK only after the result and checkpoint are durable.

## Redis
Celery broker/queue transport and optional ephemeral progress cache. Transient coordination — never the
authoritative Job state store.

## PostgreSQL
Job / Upload Session / outbox / current state / append-only event history / checkpoints / leases /
attempts / provenance / object references, with atomic constraints (unique keys, transactional Outbox).

## Object Storage
Original 500 MB documents and large/derived artifacts; immutable object versions; multipart direct
upload; scoped short-lived access. The data plane for large bytes.

## Kubernetes / Day27
Separate API and worker Deployments; worker HPA from queue pressure; Rolling Update/rollback of compute;
readiness vs business correctness; the replaceable Pod boundary.

## Monitoring / Observability
Operational signals and cross-component explanation using metrics, structured logs, traces, durable
business state/events, and stable correlation identity.

No Playwright connection is used; it is not forced in.

---

# AI Backend Connections

```text
- RAG document ingestion: upload -> parse -> chunk -> embed -> index -> expose result.
- Expensive provider calls, rate limits, retry storms, duplicate cost, and provider_request_id evidence.
- Stable idempotency keys incorporating document/chunk/model version.
- A wrong embedding model is a production SEMANTIC failure that still passes readiness.
- Model/release/data provenance and versioned vector indexes enable safe repair and alias switching.
- Immutable originals are durable source data; embeddings/indexes are derived, rebuildable data.
- Business verification includes real RAG output quality, not merely process health or HTTP 200.
```

---

# English Interview

Key vocabulary: control plane, data plane, `202 Accepted`, job_id, source of truth, broker,
transactional outbox, at-least-once, idempotency key, unique constraint, upsert, lease, checkpoint,
presigned URL, multipart upload, Upload Session, checksum, TOCTOU, exponential backoff, jitter, circuit
breaker, queue depth, oldest-age, throughput, cardinality, trace_id, provenance, invalidate, reprocess,
index alias.

## Beginner

Question:

Why should a long-running job run in a Celery worker instead of inside the FastAPI request?

Actual student attempt (preserved):

> "because long time response influence next request."

Technical/English review: the idea (long responses hurt other requests) is right but incomplete and
ungrammatical; add HTTP timeouts and lifecycle decoupling.

Strong Answer:

> A long-running job should run in a Celery worker because keeping it inside the FastAPI request can
> cause HTTP timeouts and consume API capacity. A worker decouples the job lifecycle from the request,
> so the job can continue after the client disconnects or the API Pod restarts.

## Intermediate

Question:

Which component owns which state: PostgreSQL, Redis, or Object Storage?

Actual student attempt (preserved):

> "the postgresql restore state and Object Storage key ,redis restore queue and Object Storage restore document"

Technical/English review: correct mapping, but "restore" should be "stores", and Redis is the broker
(delivers), not the owner.

Strong Answer:

> PostgreSQL stores durable job state, metadata, and object references. Redis acts as the Celery broker
> and delivers task messages, but it is not the source of truth for the job. Object Storage stores the
> original documents and large generated results.

## Senior

Question:

Under at-least-once delivery, how do you prevent duplicate durable effects and minimize duplicate
provider calls, and what risk still remains?

Actual student attempt (preserved):

> "我忘了"

Teaching note: the student blanked, so the senior answer was taught directly.

Strong Answer:

> I would assume at-least-once delivery and make the worker idempotent. Each embedding operation would
> use a stable key based on the job ID, chunk hash, and model version. I would store durable step
> checkpoints in PostgreSQL and use a unique constraint or idempotent upsert for the embedding result.
> The worker would acknowledge the queue message only after the result and checkpoint were persisted.
> If the task were delivered again, the new worker would detect the completed step and skip the
> duplicate model call and write. For an external provider or vector store, I would also use provider
> idempotency keys or stable vector IDs where supported and reconcile remaining dual-write gaps; I would
> not claim exactly-once across independent systems.

---

# Mental Model Summary

```text
FastAPI accepts/exposes. Celery executes. Queue/Redis transports. PostgreSQL owns durable truth.
Object Storage owns large bytes. Monitoring detects known abnormal signals. Observability explains
internal behavior. At-least-once requires idempotent effects. Compute rollback does not repair data.
```

```text
HTTP request lifecycle   != long-running job lifecycle
202 + job_id             = a durable business commitment (already in PostgreSQL)
Transactional Outbox     = atomic (business state + intent-to-publish), still at-least-once
Idempotency key + unique = duplicate durable-write control (not exactly-once across systems)
Lease                    = exclusive attempt ownership with expiry; ACK after durable write
Object key               != authorization
Oldest queue age         ~ SLO; correlate with depth + throughput
job_id (stable)          = correlation identity; job_status changes; keep metrics low-cardinality
Contain -> restore -> identify -> rebuild -> verify/re-expose (data repair != compute rollback)
```

Preserve the student's actual final synthesis:

> "fastAPI做应用层面的功能，比如接收请求处理请求，返回job_id。celery 安排work去queue中消耗job。redis传递任务信息与缓存。postgresql保存持久化数据状态，包括job state，存储对象引用等。object storage存储输入文档以及生成文档，monitoring负责检测预定指标 Observability负责根据很多层面解释发送事件。因为没有将状态存入数据库，所以服务重启以后只能去持久化数据中获取信息。通过设置幂等key以后，第二次先查询数据库使用upsert,就可以避免二次投递。代码回滚，不代表数据库的持久化数据也进行了回滚。以及object storage已经生成的文档回滚"

Narrow corrections to that synthesis:

```text
1. The sentence "没有将状态存入数据库，所以服务重启以后只能去持久化数据中获取信息" is inconsistent:
   BEFORE returning 202 you DO store the accepted Job in PostgreSQL; after a restart, memory/broker are
   not the truth — PostgreSQL is the durable recovery source.
2. "先查询数据库使用upsert" can race; enforce a DB unique constraint + atomic upsert. It prevents
   duplicate durable writes for that key, not a duplicate external model call already made.
3. Redis transports/caches; it is not durable truth. PostgreSQL owns the Job.
4. Compute rollback is correct as incomplete; add explicit identify/quarantine/invalidate/reprocess/
   verify/re-expose for persisted DB state, Object Storage artifacts, and vector indexes.
5. Assume at-least-once; design idempotent effects; do not promise exactly-once across independent systems.
```

---

# Today's Takeaway

```text
Most important mental model:
Deploying components is not architecture. Define responsibility, state/data ownership, delivery
guarantees, failure boundaries, recovery policy, and the evidence that proves business correctness.
FastAPI accepts/exposes, Celery executes, Queue/Redis transports, PostgreSQL owns truth, Object Storage
owns bytes.

Most important production risk:
At-least-once delivery + external side effects mean you must design idempotent effects and never claim
exactly-once. Readiness 200 is not business correctness, and compute rollback does not repair data.

Most important framework/AI connection:
RAG ingestion with a Transactional Outbox, durable checkpoints/leases, idempotency keys with a unique
constraint, presigned multipart upload + Upload Session, bounded classified retries, and versioned
indexes with alias switching for safe data repair.

Most important interview answer:
Assume at-least-once, make effects idempotent with a stable (job_id, chunk_hash, model_version) key and
a unique constraint, ACK after durable write, and reconcile external systems; do not promise
exactly-once.
```

Scope honesty: the Day28 artifact is conceptual architecture documentation. No FastAPI/Celery service,
Redis broker, PostgreSQL schema, Object Storage bucket, vector index, Kubernetes workload, metrics
backend, log pipeline, or tracing system was created or run; no static code/config/schema validation,
queue redelivery, provider failure, load, smoke, rollback, or data-repair test was executed. See the
blueprint's validation-limitations section for the future runtime validation plan.

---

# Before Next Lesson Checklist

- [ ] Can I explain why the request and the job are different lifecycles, and what `202 + job_id` commits?
- [ ] Can I assign every job state/byte to PostgreSQL, Redis, Object Storage, or memory and defend it?
- [ ] Can I explain the DB→queue crash gap and the Transactional Outbox, and why it is still at-least-once?
- [ ] Can I design a durable checkpoint + lease + idempotency key with a unique constraint, ACKing last?
- [ ] Can I design presigned multipart upload with an Upload Session and server-side verification?
- [ ] Can I design a bounded, classified retry policy with jitter and a circuit breaker?
- [ ] Can I pick queue signals (depth/oldest-age/throughput) and a stable correlation identity?
- [ ] Can I order contain → restore → identify → rebuild → verify and explain why rollback doesn't repair data?
- [ ] Can I answer beginner, intermediate, and senior production-architecture questions in English?
