# Backend Data Design Capstone (Day42)

The Phase 3 capstone design for the AI Backend Data Layer. It integrates the durable PostgreSQL truth
(Day29-Day37), the transient Redis coordination/acceleration (Day38-Day41), and the Object Storage artifact
boundary into **one** failure-aware ownership, recovery, and verification contract for a multi-tenant AI
Research and Automation Platform.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No PostgreSQL, Redis, Object Storage, Provider,
> Celery/Relay/Worker, FastAPI, migration, or `EXPLAIN ANALYZE` command was executed; no failover, load,
> security, or data-repair test was run. `EXPLAIN ANALYZE` and disposable-environment measurement are
> described as a **future validation method**, not a performed result. SQLAlchemy/Alembic are Phase 4 and are
> **not** implemented here. Key names, IDs, and thresholds are static design examples. Contains **no secrets,
> real connection strings, or client data**.

Related: [Day42 lesson](../../docs/redis/day42-backend-data-design-capstone.md) ·
[Day41 coordination design](redis/redis-coordination-and-production-safety-design.md) ·
[Day40 messaging design](redis/redis-messaging-and-queue-semantics-design.md) ·
[Day39 cache design](redis/redis-cache-consistency-design.md) ·
[Day38 acceleration design](redis/redis-acceleration-layer-design.md) ·
[Day37 reliability runbook](runbooks/postgresql-production-reliability.md) ·
[project README](README.md)

---

## 1. Ownership and lifecycle map (who owns what)

```text
PostgreSQL (DURABLE BUSINESS AUTHORITY):
  Job identity/status, tenant ownership, API idempotency uniqueness (tenant_id, idempotency_key),
  Outbox dispatch intent, Attempt/Event lifecycle, durable current_fencing_generation, Artifact references
  + verification metadata.
Object Storage (LARGE BYTES):
  Document input bytes and Result Artifact bytes, addressed by deterministic keys; PostgreSQL owns their
  durable references + hash/size/verification metadata.
Redis (TRANSIENT COORDINATION / ACCELERATION, LOSABLE):
  cache entries, queue messages, rate-limit counters, short leases. May be lost on eviction/failover and
  CANNOT prove a Job was accepted or completed.
```

Per-entity ownership:

| Entity | Owner | Notes |
| --- | --- | --- |
| Upload Session | PostgreSQL | tenant-owned; verified state, key, hash/size, expiry before Job admission |
| Document | Object Storage (bytes) + PostgreSQL (reference) | large bytes in Object Storage; durable reference/provenance in PostgreSQL |
| Job | PostgreSQL | durable identity/status/tenant; the acceptance truth |
| Attempt | PostgreSQL | per-execution record; may not exist until a Worker claims |
| Event | PostgreSQL | append-only history; never edited |
| Outbox | PostgreSQL | dispatch/notification intent committed with the state change |
| Result Artifact | Object Storage (bytes) + PostgreSQL (reference) | deterministic key; reference + verification metadata durable |
| cache entries / messages / counters / leases | Redis | transient, tenant-scoped, losable; never business truth |

---

## 2. Acceptance contract (what is durable at 202)

```text
POST /jobs Accept transaction (ONE PostgreSQL transaction) commits BEFORE 202:
    INSERT Job(status = queued, tenant_id, ...)
  + enforce UNIQUE (tenant_id, idempotency_key)      -- create-or-return the same Job
  + INSERT Outbox(dispatch intent)
  COMMIT -> 202 + job_id

Required durable facts at 202: Job + (tenant_id, idempotency_key) uniqueness + Outbox dispatch intent.
NOT required at 202: Attempt, Event, lease token, fencing generation — these appear only at claim/takeover.
Redis messages/cache/counters/leases are NOT part of acceptance and cannot prove a Job was accepted.
```

---

## 3. Dispatch and duplicate delivery

```text
Relay: scan Outbox intents WHERE published_at IS NULL -> publish to the queue -> checkpoint published_at.
Do NOT scan all queued Jobs: `queued` is a business state, not a durable statement to emit a dispatch now.
Relay crash AFTER publish but BEFORE checkpoint -> expected at-least-once DUPLICATE delivery.

Workers accept duplicate delivery as NORMAL and prevent duplicate business work with a PostgreSQL GUARDED
transition (only one queued -> running succeeds). A Redis "processed" marker is an optional optimization,
never final truth.
```

---

## 4. Completion and Artifact reconciliation

```text
Provider call and Object Storage write happen OUTSIDE any long PostgreSQL transaction.

Short guarded completion transaction (ONE PostgreSQL transaction):
    record Result Artifact reference
  + finish the current Attempt
  + Job running -> succeeded
  + append job_succeeded Event
  + create a notification Outbox intent if needed
  guarded by: job_id AND job_status = 'running' AND lease_token = current token
              AND lease_expires_at > now() AND fencing_generation = current persisted generation (EQUALITY)

Artifact existence ALONE does not mean the Job succeeded. Before completion, verify:
  - Artifact identity / integrity / Job-Attempt ownership (deterministic key + hash)
  - current PostgreSQL ownership (the guard above)
  - Provider / result evidence (stable Provider idempotency)

If Object Storage write succeeded but the PostgreSQL completion rolled back: do NOT blindly delete the
Artifact or re-call the Provider. The current valid owner reconciles deterministic Artifact metadata + Provider
idempotency/result evidence, then retries ONLY the short guarded completion transaction when appropriate.
```

---

## 5. Failure priority and degraded modes

| Failure | Behaviour | Why |
| --- | --- | --- |
| Redis loses a dispatch message | Relay recovers it from the PostgreSQL Outbox | Outbox is the durable dispatch intent |
| Redis unhealthy | **fail closed** on new expensive admission; do not treat a low/missing counter as quota headroom; no Worker mass-restart; bounded backoff for new Redis coordination; drain/preserve in-flight external work | a losable counter is not proof of headroom |
| PostgreSQL unavailable | do **not** accept new `POST /jobs` (Job + idempotency uniqueness + Outbox cannot atomically commit); preserve already-created external result/Artifact evidence; reconcile after recovery | acceptance atomicity lives only in PostgreSQL |
| Input Object Storage unavailable / Upload Session unverifiable | **fail closed** for the affected Job admission only; do **not** stop unrelated healthy endpoints or the whole container | never accept a Job with an unverified input; scope the failure |

---

## 6. Upload / Document contract

```text
Before accepting a Job that references an upload_session_id, verify ALL of:
  - authenticated tenant ownership of the session
  - completed / verified session state
  - non-expiry
  - a registered Object Storage key
  - expected or verified hash / size
  - relevant content-type / scanning policy
Otherwise fail closed for that admission (do not create a Job with an unverified input).
```

---

## 7. Tenant isolation, audit, and retention

```text
Cache keys include tenant identity, e.g. job-summary:{tenant_id}:{job_id}:v1 -- but a key is NOT authorization.
API/DB reads MUST use the trusted authenticated tenant AND query by BOTH tenant and Job identity: a globally
unique Job UUID still leaks data if another tenant learns it and the query filters by job_id alone.

Composite uniqueness prevents duplicate association; composite tenant-aware foreign keys prevent a Tenant A Job
-> Tenant B Document link. e.g. job_documents(tenant_id, job_id, document_id) references BOTH the
(tenant_id, job_id) and (tenant_id, document_id) parent boundaries.

Manual repair must NOT only mutate `jobs`: update the relevant Attempt if appropriate and APPEND an immutable
audit/Event record (tenant, Job/Attempt, actor/system, action, reason, time, incident/repair reference,
correlation/evidence).

Retention: on Artifact retention expiry, delete Object Storage bytes per policy but RETAIN a tombstoned/expired
Artifact reference (key/checksum/created/deleted/policy). NEVER edit an append-only Event; APPEND a new
artifact_expired / artifact_deleted Event with reason and evidence.
```

---

## 8. Performance evidence method (future validation, not run)

```text
Do NOT claim an index is required from intuition. In a DISPOSABLE isolated environment, collect:
  representative schema / index / data distribution / query parameters,
  EXPLAIN ANALYZE, actual vs estimated rows, timing, and (where useful) buffers,
  comparing the before/after index state.
This is DISPOSABLE RUNTIME EVIDENCE, not production validation. In this capstone it is a described METHOD only
-- EXPLAIN ANALYZE was NOT run.
```

---

## 9. Fencing-generation migration (Expand -> Contract)

```text
Add current_fencing_generation via: Expand -> compatible deploy -> backfill -> validate -> switch -> contract.
  - New code tolerates NULL during rollout.
  - claim/takeover writes a strictly GREATER durable generation.
  - validate all relevant running Jobs and completion paths BEFORE enforcing the new guard.

Do NOT shorten a lease to force takeover, and do NOT assume fencing magically stops old binaries: lease expiry
permits takeover ONLY. An old Worker that bypasses the new guard can still write a stale completion. Therefore
DRAIN/UPGRADE old Workers, or enforce the guard on EVERY durable completion path; reconcile Provider/Artifact
before a new valid owner acts. (Day36 discipline; SQLAlchemy/Alembic are Phase 4.)
```

---

## 10. Integrated failure / recovery runbook

Scenario: PostgreSQL committed Job + Outbox and returned 202; a Redis failover lost some counters/messages
(Relay republishes durable Outbox intent); old Worker A called the Provider and paused, its lease expired, and
Worker B took over with a larger durable fencing generation and found a deterministic Artifact.

| Step | Action | Why |
| --- | --- | --- |
| 1 | Contain old Worker A's claims; ensure the legacy completion path cannot bypass the new guard | expiry does not stop a paused A or old code |
| 2 | Do **not** mass-restart Workers | mass restart interrupts in-flight external work |
| 3 | Relay republishes the durable Outbox intent | Redis message loss is recovered from PostgreSQL |
| 4 | Reconcile Job / Attempt / Provider idempotency / Artifact | durable facts + idempotency decide reality |
| 5 | Then either perform the guarded atomic completion, or let ONLY the current owner decide a verified next Provider action | the guard + fencing equality reject a stale writer |

```text
NEVER blindly re-call the Provider merely because B has a fresh lease.
NEVER use Artifact existence as a substitute for ownership + result verification.
```

---

## Capstone one-screen summary

```text
ownership    -> PostgreSQL durable truth; Object Storage bytes; Redis transient/losable coordination
acceptance   -> Job + (tenant_id, idempotency_key) UNIQUE + Outbox committed in ONE tx BEFORE 202
dispatch     -> Relay publishes unpublished Outbox intents; at-least-once duplicates are normal
duplicate    -> PostgreSQL guarded transition (one queued->running); Redis markers are optional
completion   -> short guarded tx (Artifact ref + Attempt finish + running->succeeded + Event); verify identity+ownership+result
degraded     -> Redis unhealthy=fail-closed admission; PostgreSQL down=no new accepts; input Object Storage down=fail-closed that admission only
tenant       -> authenticated tenant predicate + composite tenant-aware FKs; a key is not authorization
audit/retain -> append-only Events; tombstone Artifact references; never edit history
performance  -> disposable EXPLAIN ANALYZE evidence (a METHOD here, NOT run); not production validation
fencing      -> durable generation via Expand->Contract; drain/upgrade old Workers; expiry != a stop
recovery     -> contain + reconcile (Job/Attempt/Provider idempotency/Artifact) + guarded completion; never blind re-call, never Artifact-as-ownership
```

---

## Future boundaries (not implemented here)

```text
Day43     exposes this Day42 ownership/failure contract as the FastAPI AI Job HTTP product contract
Day44     typed Pydantic v2 input/output + error contracts
Day46-48  SQLAlchemy mapping of THIS model (no ownership change), transactional persistence, Alembic evolution
Phase 4+  a runnable backend; this capstone stays conceptual/static design
```

---

## Validation and evidence classification

```text
CONCEPTUAL / DESIGN     : the ownership/lifecycle map, acceptance contract, dispatch/duplicate handling,
                          completion + Artifact reconciliation, failure/degraded matrix, upload contract,
                          tenant/audit/retention model, fencing migration, and recovery runbook are design
                          decisions and stated invariants integrating Day29-Day41.
STATICALLY REVIEWED     : SQL-shaped and key-shaped examples (guard predicate, composite FKs, cache keys,
                          Outbox scan) are read for shape and naming only.
RUNTIME NOT RUN         : no PostgreSQL, Redis, Object Storage, Provider, Celery/Relay/Worker, or FastAPI
                          command was executed; no migration and no EXPLAIN ANALYZE were run.
DISPOSABLE RUNTIME       : NOT RUN -- EXPLAIN ANALYZE / disposable-environment measurement is a described
                          future method, with no collected plan/timing/rows.
FAILOVER/LOAD/SECURITY   : NOT RUN -- no failover, load, security, or data-repair drill was executed.
PRODUCTION NOT VALIDATED : not deployed; no production accessed; every key/ID/threshold is a static example.
SECURITY                 : no secrets, credentials, connection strings, or client data; identifiers are placeholders.
SCOPE                    : SQLAlchemy/Alembic are Phase 4 and not implemented; no runnable rate limiter, real
                          Worker, real Object Storage integration, real schema change, real queue, real
                          Provider call, or runtime test is claimed.
```
