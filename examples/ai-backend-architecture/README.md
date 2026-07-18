# examples/ai-backend-architecture

Day28 **Production AI Backend Architecture Blueprint** — a conceptual, teaching-only design for a RAG
document-ingestion backend (FastAPI, Celery, Redis, PostgreSQL, Object Storage, Monitoring,
Observability).

**Conceptual only.** This is architecture documentation, **not** a runnable service. No FastAPI/Celery
app, Redis broker, PostgreSQL schema, Object Storage bucket, vector index, Kubernetes workload, metrics
backend, log pipeline, or tracing system is created or run here. No real secret, credential, presigned
URL, or customer document is included.

Lesson: `docs/devops/day28-ai-backend-production-architecture.md`

## Scenario

A user uploads a 500 MB document via `POST /documents`; parse → chunk → embed → index takes ~8 minutes.
Doing that inside the HTTP request causes Ingress timeout, client retry, duplicate model cost, unclear
progress, and lost in-memory state on API Pod replacement. The blueprint fixes this with an
accept-fast / process-async design and clear ownership.

## 1. Responsibility map

```text
FastAPI        -> control plane: authn/authz, validate, issue presigned URL, verify upload,
                  create durable Job (+ Outbox) in one transaction, return 202 + job_id, expose status/result.
Celery worker  -> execute the long pipeline; retry/ACK; NOT the Job source of truth.
Queue / Redis  -> transport/deliver task messages; optional ephemeral progress cache. NOT durable truth.
PostgreSQL     -> durable truth: Job lifecycle, metadata, Outbox, append-only events, checkpoints,
                  leases, attempts, provenance, object references, unique constraints.
Object Storage -> large bytes: immutable originals + derived artifacts; object versions; scoped access.
Monitoring     -> evaluate known signals vs thresholds/SLOs; drive alerts.
Observability  -> explain internal behavior via metrics + structured logs + traces + durable events.
```

One-line model: **FastAPI accepts/exposes. Celery executes. Queue/Redis transports. PostgreSQL owns
durable truth. Object Storage owns large bytes. Monitoring detects. Observability explains.**

## 2. Request / upload / job flow

```text
1. Client -> POST /documents (authn/authz)
2. FastAPI -> create Upload Session (INITIATED), choose server-controlled object key,
              issue short-lived presigned (multipart) upload URL
3. Client -> upload 500 MB DIRECTLY to Object Storage (multipart; not through FastAPI)
4. Client -> POST /documents/{id}/complete   (UNTRUSTED trigger)
5. FastAPI -> verify object existence, size, checksum/version, ownership, required scan
              -> Upload Session VERIFIED
6. FastAPI -> ONE PostgreSQL transaction: INSERT Job (QUEUED) + INSERT Outbox event
              (Job bound to immutable object version/checksum)
7. Outbox relay -> publish unsent events to Queue -> mark sent
8. Celery worker -> claim (lease) -> PARSE -> CHUNK -> EMBED -> INDEX -> checkpoints in PostgreSQL
              -> ACK only after result + checkpoint are durable
9. Client -> GET /jobs/{job_id} -> PostgreSQL-backed status/result reference
```

## 3. State machines

```text
Upload Session:  INITIATED -> UPLOADING -> VERIFIED | FAILED | EXPIRED
Job:             QUEUED -> RUNNING -> RETRY_WAIT -> (RUNNING ...) -> SUCCEEDED | FAILED_TERMINAL
Repair path:     SUCCEEDED -> INVALIDATED -> REPROCESSING -> SUCCEEDED   (event history preserved)
Durable stages:  UPLOADED -> PARSED -> CHUNKED -> EMBEDDING -> INDEXED -> SUCCEEDED
```

## 4. State / data ownership table

| Data | Owner | Notes |
|---|---|---|
| Job lifecycle state (all states) | PostgreSQL | source of truth after `202`; not memory/broker |
| Job metadata (owner, checksum, version, attempt, stage, timestamps, error, result ref, provenance) | PostgreSQL | durable |
| Outbox events | PostgreSQL | atomic with the Job insert; relay publishes |
| Append-only transition history (`job_events`) | PostgreSQL | attempts, failures, invalidation, recovery |
| Checkpoints / leases | PostgreSQL | resume location + exclusive ownership with expiry |
| Task messages (delivery) | Queue / Redis | transient; at-least-once |
| High-frequency UI progress cache | Redis (optional) | transient; reconstructable |
| Request-local/transient data | FastAPI memory | never durable truth |
| 500 MB originals + large derived artifacts | Object Storage | immutable versions; scoped access |
| Object bytes reference (key/version/checksum) | PostgreSQL | pointer only; bytes live in Object Storage |

## 5. Delivery, outbox, and idempotency boundaries

```text
- You cannot atomically write two independent systems (PostgreSQL + broker).
- Transactional Outbox makes (business state + intent-to-publish) atomic INSIDE PostgreSQL.
- Relay may publish then crash before marking sent -> possible duplicate publish.
- Therefore: at-least-once delivery + idempotent processing (never claim exactly-once).
- Idempotency key: stable business identity, e.g. (document_id, chunk_hash, model_version).
- Enforce with a DB UNIQUE constraint + idempotent upsert; check durable state before repeating work.
- ACK the queue message ONLY after result + checkpoint are durably recorded.
- External calls: use provider idempotency keys if available; a provider call that succeeds before the
  local checkpoint write can still be repeated on redelivery (cost). Reconcile dual-write gaps.
- Separate vector store: stable vector IDs + idempotent upsert + versioned indexes + reconciliation.
```

## 6. Retry policy

```text
- Exponential backoff + JITTER.
- Bound by MAX ATTEMPTS and/or an overall RETRY DEADLINE (a max delay alone allows infinite attempts).
- Classify: 429 (honor Retry-After, rate-limit) | 503/timeout (retry in policy) |
            400/parse (terminal) | 401/403/config (stop/contain globally + alert).
- Global rate limiter / circuit breaker when the provider is degraded.
- Persist: attempt_count, next_retry_at, last_error, retry_deadline, provider_request_id.
- Retry is a controlled recovery policy, not an infinite loop.
```

## 7. Failure / rollback / data-repair matrix

| Concern | Compute rollback (Day27) | Data repair (Day28) |
|---|---|---|
| Stops future bad compute | Yes | — |
| Fixes persisted PostgreSQL state | No | Yes (invalidate/reprocess) |
| Fixes Object Storage artifacts | No | Yes (rebuild from immutable originals) |
| Fixes vector/index entries | No | Yes (versioned rebuild + alias switch) |
| Undoes external side effects | No | Only via compensation/reconciliation |

Ordered runbook (wrong embedding model that passed readiness):

```text
A. Pause/contain bad v2 workers first (no new wrong results).
B. Restore known-good v1 desired release; verify model/config + readiness.
C. Identify + quarantine/invalidate affected results by provenance (job_id, worker_release,
   processing_version, embedding_model/version, index namespace/version, source checksum, completed_at).
D. Idempotently reprocess from immutable originals into a clean/versioned index.
E. Verify counts, model/version/dimensions, real RAG quality, errors, latency, cost, Job success;
   then switch the index alias/current pointer and restore normal processing.
```

`Compute rollback stops future damage. Data repair corrects damage already persisted.`

## 8. Monitoring and observability signals

```text
Monitoring (known signals vs thresholds/SLOs):
  API:      request rate, error rate, latency
  Queue:    depth, OLDEST age, enqueue/dequeue rate
  Worker:   active workers, task duration, completion throughput, retry rate, terminal failures
  Provider: latency, 429/503, cost
  Business: end-to-end Job latency, success rate, stuck jobs by stage
  Interpretation: depth+age rising + throughput ~0 -> stall; + throughput normal -> under capacity;
                  depth high + age low -> recent burst.

Observability (explain WHY):
  Correlate on STABLE job_id (job_status changes and is shared -> not an identifier).
  Scopes: trace_id (request path), attempt_id/count (application-owned), broker task_id (delivery,
          may change), provider_request_id (provider-side evidence).
  Structured logs: service, job_id, trace_id, task_id, attempt_id/count, stage, state, duration, safe
          error code. Keep metric labels LOW-cardinality (job_id belongs in logs/traces, not labels).
  Durable history: jobs.current_status (projection) + append-only job_events (history).
```

## 9. Security boundaries

```text
- Short-lived, scoped presigned access; server-controlled object keys; tenant ownership/isolation.
- Verify checksum/object version; bind the Job to an immutable version (avoid overwrite/TOCTOU).
- An object key is NOT authorization.
- Never log document content, presigned URLs, keys, tokens, passwords, or unnecessary personal data.
- Least privilege for every component; no real secrets or customer documents committed to the repo.
```

## 10. Validation limitations (honest)

```text
Completed in class (conceptual review only):
  responsibility boundaries, state machines, retry/idempotency logic, failure-containment order,
  rollback-vs-data-repair distinction, observability signal choices.

Performed during this repository update:
  Markdown structure/link checks and a repository secret scan on the changed files.

NOT performed / NOT verified (no such system was built or run):
  static code/config/schema validation, DB migration, queue redelivery, provider failure injection,
  load test, smoke test, runtime rollback, and data repair.
```

### Future runtime validation plan (planned, NOT run)

```text
1. Stand up FastAPI + Celery + Redis + PostgreSQL + Object Storage (dev) and apply a real schema.
2. Contract tests: 202 + job_id, status API, presigned upload + server-side verification.
3. Outbox relay test: crash between commit and publish -> reconcile; assert no lost/lonely QUEUED job.
4. Idempotency test: redeliver a task -> assert one durable write per (document_id, chunk_hash, model_version).
5. Retry test: inject 429/503/timeout + a 20-minute outage -> assert backoff+jitter, caps, circuit breaker.
6. Failure/repair drill: wrong-model release -> contain, restore, invalidate by provenance, rebuild a
   versioned index, verify RAG quality, switch alias.
7. Observability check: trace one job_id end-to-end; confirm low-cardinality metrics and safe logs.
```

> Phase 3 (Backend Foundations: PostgreSQL, SQL, Redis, Database Design) will deepen the durable-data,
> transaction, and schema design boundaries introduced here.
