# Redis Cache Consistency Design

Day39 design artifact for the AI Backend Data Layer. It turns the Day38 ownership boundary (PostgreSQL owns
durable Job truth; Redis is a bounded, rebuildable acceleration layer) into an **explicit per-endpoint cache
consistency contract**: how each endpoint reads, invalidates, expires, handles a miss, tolerates staleness,
degrades on failure, and is observed for correctness — not just hit rate.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, cache API, PostgreSQL
> integration, Outbox Relay, Worker, Provider, Object Storage, benchmark, cache stampede, eviction, hot key,
> TTL, jitter, or production system was run or measured. Cache keys, TTLs, and jitter ranges are **static
> design examples**, not measured results or production recommendations. Contains **no secrets or real
> connection strings**.

Related: [Day39 lesson](../../../docs/redis/day39-redis-cache-design-and-consistency.md) ·
[Day38 acceleration-layer design](redis-acceleration-layer-design.md) ·
[project README](../README.md) ·
[Day37 production reliability runbook](../runbooks/postgresql-production-reliability.md)

---

## 1. Ownership recap (the boundary Day39 builds on)

```text
PostgreSQL app.jobs = AUTHORITATIVE Job lifecycle/audit truth (a COMMIT is the moment of authority).
Object Storage      = large bytes (PDFs, Result Artifacts). Cache carries API VIEWS, never large payloads.
Redis cache         = a rebuildable PROJECTION of PostgreSQL truth. It may be STALE or ABSENT.

A cache hit is never proof of truth; a cache miss is never a Job failure. Every cache decision is judged
against the committed PostgreSQL state, not against the cached value.
```

---

## 2. Cache-aside read contract

```text
READ path (cache-aside):
  1. GET the cache key.
  2. HIT  -> return the cached view ONLY when the endpoint's semantics tolerate that staleness.
  3. MISS -> read authoritative data from PostgreSQL, return it, then BEST-EFFORT repopulate Redis with a TTL.
  4. A cache WRITE failure must NOT invalidate an already-correct PostgreSQL response.
```

The read never lets the cache override PostgreSQL. On a miss the authoritative answer is already in hand
before Redis is touched again, so a failed `SET` degrades to "no cache this time", not to a failed request.

---

## 3. Invalidation contract (commit first, then invalidate)

```text
WRITE / state-transition path:
  1. Worker COMMITS the PostgreSQL state transition first (e.g. running -> succeeded).
  2. ONLY AFTER commit, invalidate EVERY affected cache view.
  3. A stale window still exists between commit and invalidation completing -- Redis is a view, not truth.

Why not delete before commit:
  pre-commit delete races -> another request misses cache -> reads OLD running from PostgreSQL
                          -> re-caches the stale running state BEFORE the commit lands. The cache is now
                             wrong with a fresh TTL.

Why not write-through the guessed final view:
  the baseline is INVALIDATE-AFTER-COMMIT, not writing a guessed "succeeded" view directly into Redis;
  a guessed write has concurrency / retry / ordering risk.
```

### Every affected view must be invalidated

```text
On running -> succeeded, invalidate BOTH:
  - ai:tenant:{tenant_id}:job-detail:v1:{job_id}          (the Job-detail view)
  - ai:tenant:{tenant_id}:recent-completed-jobs:v1        (the tenant recent-completed list)
Invalidating only the detail leaves the recent-completed list inconsistent.
```

---

## 4. Cache representation and versioning

```text
Cache JSON is a CONSUMER CONTRACT (clients parse the shape and the meaning of each field).

Incompatible change  -> new versioned key (v2) while old and new APIs coexist.
  example: progress 42 (integer 0-100)  ->  0.42 (float 0-1) is INCOMPATIBLE: same field, different meaning.
           ai:tenant:{t}:job-detail:v1:{job}   (progress = 0..100)
           ai:tenant:{t}:job-detail:v2:{job}   (progress = 0..1)
Compatible change    -> an additive OPTIONAL field does NOT automatically require a new key version.
```

---

## 5. TTL, jitter, and expiry load

```text
Fixed synchronized TTL across many keys -> CACHE AVALANCHE: many DISTINCT keys expire together and all
                                           fall back to PostgreSQL at once.
TTL jitter (e.g. base +/- a random spread) -> distributes expiry over time.

Single-flight protects ONE hot key after a miss; it does NOT solve one million DISTINCT keys expiring
together. Jitter is the tool for synchronized expiry; single-flight is the tool for one hot key.
```

---

## 6. Stampede, single-flight, and stale-while-revalidate (SWR)

```text
Hot-key stampede: many requests miss the SAME key at once.
  -> elect ONE leader to read PostgreSQL / rebuild the value.
  -> followers WAIT only within a BOUNDED deadline, or receive an ALLOWED stale value.
  -> on leader timeout, do NOT fan out all followers to PostgreSQL. Use bounded retry, exponential
     backoff + jitter, circuit/backoff behaviour, and endpoint-specific degradation.

Stale-while-revalidate:
  a normal Job-progress view MAY return a short stale `running` view while ONE background refresh obtains
  PostgreSQL truth. SWR is NOT allowed for state-changing / sensitive operations.
```

---

## 7. Fail-open vs fail-closed (by endpoint sensitivity)

| Endpoint | Sensitivity | On cache/Redis trouble | Why |
| --- | --- | --- | --- |
| `GET /jobs/{job_id}/progress` | read, tolerant | **fail-open** / controlled degradation may be acceptable (bounded SWR, short stale `running`) | a slightly stale progress number does not corrupt state |
| `POST /jobs/{job_id}/cancel` | state-changing, sensitive | **fail-closed** — PostgreSQL authorization **plus** a guarded state transition | a cache cannot authorize a cancel; even a PostgreSQL pre-read is not a substitute for the guarded write |

```text
A cache value can never AUTHORIZE a sensitive write. The guarded PostgreSQL write (the Day33/Day34 pattern)
is the only authority for cancellation; a stale cache saying `running` must not drive a cancel decision.
```

---

## 8. Negative caching and cache penetration

```text
Cache penetration: random NON-EXISTENT Job IDs miss cache every time and hit PostgreSQL (attack or a broken
                   client).
Defence: a SHORT, TENANT-SCOPED negative cache ("this id does not exist") absorbs the repeated misses.

Rules:
  - keep it SHORT-LIVED.
  - successful Job creation INVALIDATES the negative entry (so a real new Job is visible).
  - a negative cache is NEVER a security / authorization decision -- it only protects PostgreSQL from load.
```

---

## 9. Hot keys and cache-health observability

```text
A cache HIT can still overload Redis: 50,000 requests to ONE key / node / network path is a hot key.
A HIGH HIT RATIO does NOT prove cache health.

Observe (not just hit ratio):
  - Redis latency, CPU, network
  - per-key / per-tenant hotness
  - memory + eviction
  - PostgreSQL fallback pressure (pool waits)
  - correctness / freshness (below)
```

---

## 10. Correctness metrics (freshness, not just efficiency)

```text
Hit/miss ratio measures cache EFFICIENCY, not TRUTH.

Correctness signals to measure:
  - PostgreSQL commit -> invalidation delay / failure / backlog
  - cache age (how old is the served view)
  - stale TERMINAL responses (a `succeeded` Job still served as `running`)
  - sampled Redis-vs-PostgreSQL agreement
  - API latency
  - Redis eviction / memory
  - PostgreSQL pool waits under fallback
```

---

## 11. Invalidation recovery (Outbox + retryable idempotent DEL)

```text
Scenario: PostgreSQL committed `succeeded`; the cache DEL network call times out -> delete outcome UNKNOWN.

Do NOT:
  - redo the Job state transition.
  - re-call the Provider.

Do:
  - record the cache-invalidation INTENT transactionally WITH the durable state change (Transactional Outbox).
  - a Relay RETRIES an idempotent Redis DEL (deleting an already-absent key is harmless).
  - TTL bounds the residual stale window as a backstop.

Cache-delete idempotency is UNLIKE Provider retries: a Provider retry needs a stable idempotency key and
durable evidence / Artifact reconciliation; an idempotent DEL just needs to eventually run.
```

---

## 12. Integrated incident: v2 cache contract vs a timed-out invalidation

```text
Situation:
  - the v2 Job cache is deployed; PostgreSQL committed `succeeded`.
  - the invalidation Relay times out; 50,000 users still read the v1 `running` cache.

First action is NOT an automatic rollback to v1:
  - v1 is ALSO stale (it holds `running` too).
  - no evidence yet says the v2 CONTRACT is faulty.
  -> instead: retry / reconcile the cache invalidation, serve bounded SWR / single-flight for the normal UI,
     and protect PostgreSQL (bounded pools, timeouts, rate limits).

Roll back the Redis v2 cache CONTRACT/traffic ONLY IF evidence proves v2 misinterprets the data
  (e.g. v2 renders `0.42` as `42%`):
  -> roll back the v2 cache contract/traffic, invalidate v2 keys, rebuild from PostgreSQL.
  -> do NOT roll back committed PostgreSQL Job truth, and do NOT rerun Provider work.

Rollback target = the cache contract. Never the durable Job truth, never the external Provider effect.
```

---

## Cache decision summary (one screen)

```text
read            -> cache-aside: hit if tolerable, else PostgreSQL + best-effort repopulate
invalidate      -> commit PostgreSQL FIRST, then invalidate EVERY affected view
representation  -> incompatible change = new v-key; additive optional field = same version
expiry          -> TTL + jitter (avalanche control); single-flight = one hot key only
hot read        -> single-flight leader + bounded followers; SWR for tolerant reads only
sensitive write -> fail-closed on the guarded PostgreSQL write; a cache never authorizes
penetration     -> short tenant-scoped negative cache; invalidate on creation; not a security control
metrics         -> freshness/correctness (commit->invalidation delay, cache age, stale-terminal, agreement),
                   not hit ratio alone
recovery        -> Outbox invalidation intent + retryable idempotent DEL; never redo transition/Provider
incident        -> reconcile first; roll back the CACHE contract only on proven incompatibility
```

---

## Future boundaries (not designed here)

```text
Day40  Redis messaging / queue semantics (Lists / Pub-Sub / Streams, consumer groups, redelivery)
Day41  atomic multi-command composition (MULTI/EXEC, Lua), coordination, full rate-limiting algorithms
Day42  the complete data ownership + failure + recovery/verification model
Phase 4  SQLAlchemy / Alembic
```

---

## Validation and evidence classification

```text
CONCEPTUAL / DESIGN     : every cache contract, ordering rule, versioning rule, TTL/jitter reasoning,
                          stampede/SWR policy, fail-open/closed table, negative-cache rule, metrics list,
                          Outbox recovery, and the v2 incident are design decisions and stated invariants.
STATICALLY REVIEWED     : key patterns and the DEL/Outbox flow are read for shape and naming only.
RUNTIME NOT RUN         : no Redis, redis-cli, cache API, PostgreSQL, Outbox Relay, Worker, Provider, Object
                          Storage, benchmark, stampede, eviction, hot key, TTL, or jitter was executed or
                          measured. Numbers (10s, 50,000, TTL/jitter ranges) are illustrative, not measured.
PRODUCTION NOT VALIDATED: not deployed; no production cache incident, avalanche, or hot key observed.
SECURITY                : no secrets, credentials, connection strings, tenant identifiers, or production data;
                          all identifiers are placeholders.
```
