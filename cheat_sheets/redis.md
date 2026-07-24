# Redis Cheat Sheet

## Purpose

One-page review notes for Redis as the transient acceleration layer around an AI Backend's durable truth.
Built from Phase 3+ lessons (Day38+). Pair with [`interview/redis.md`](../interview/redis.md) and the
[data layer project](../projects/ai-backend-data-layer/README.md).

---

## Day38 Redis Foundations and Data Structures

Central rule:

```text
PostgreSQL app.jobs = AUTHORITATIVE Job lifecycle/audit truth
Object Storage      = large bytes (PDFs, Result Artifacts)
Redis               = small, temporary, REBUILDABLE acceleration views + lightweight broker transport
A missing Redis key is NOT missing Job truth.
```

The opening reflex to break:

```text
WRONG: progress key missing -> Job failed -> re-call Provider (invents a failure, may double-charge)
RIGHT: progress key missing -> fall back to PostgreSQL -> read the real lifecycle state
```

### Structure by access pattern

```text
String     small scalar / counter        INCR                     per-tenant request counter
Hash       named mutable fields          job-progress view        { stage, percent, updated_at }
List       ordered, duplicates allowed   latest ~20 UI activity
Set        unique membership, no order    reporting Worker IDs (a VIEW, not authority)
Sorted Set unique member + score/order    recent 100 completions (score = completion timestamp)
```

Hash vs JSON String: a JSON String forces read-modify-write, so concurrent field updates overwrite each
other; a Hash updates fields independently and `HINCRBY` bumps a counter atomically.

### Key contract

```text
ai:tenant:{tenant_id}:job-progress:v1:{job_id}
   ^tenant namespace (missing it -> cross-tenant exposure)   ^version = INCOMPATIBLE-change boundary
```

New version for an incompatible change (type, semantic, or TTL contract). An additive optional field does
**not** need a `v2`. Logical databases are a namespace, **not** isolation — share the keyspace and namespace.

### Atomicity and TTL

```text
one command      atomic (INCR, HINCRBY, HSET of one key)
two commands     NOT atomic:
                 - read percent; write percent   -> lost update (use HINCRBY)
                 - HSET ... ; EXPIRE ...          -> crash between -> permanent key (TTL never set)
TTL              a contract that a key is ALLOWED to disappear
composition      MULTI/EXEC, Lua -> Day41
```

### Memory, persistence, transport

```text
maxmemory/eviction = a CORRECTNESS boundary: only rebuildable keys may be evicted;
                     authoritative lifecycle must never live only in Redis.
RDB  snapshot  -> lose writes since last snapshot
AOF  append    -> potential loss depends on fsync policy (rewrite = log compaction / ops cost, not a loss window)
both -> smaller loss window, still NOT ownership. Truth stays in PostgreSQL (replication != backup, Day37).
Broker message = job_id + tenant_id + trace metadata. Never truth, never a 300 MB PDF (that's Object
                 Storage). 202 still returns after the durable Accept commit even if publish is unavailable.
```

### Redis outage + missing-TTL incident

```text
Outage:  fall back to PostgreSQL, but BOUNDED (Day37 connection/timeout budgets; shed/queue excess;
         serve a truthful "real-time detail temporarily unavailable"). Degrade latency, not correctness.
Missing-TTL leak:  1) detect (memory climbs, eviction hits safe keys, progress-key count only grows)
                   2) contain (ship the fix so writes set EXPIRE again)
                   3) assess with SCAN by prefix ai:tenant:*:job-progress:v1:*  (never KEYS on a hot server)
                   4) prefix-scoped TTL/delete -- NEVER FLUSHALL / FLUSHDB (shared keyspace!)
                   5) verify memory falls, safe-key eviction stops, new keys carry a TTL
```

### Weak vs strong answers (Day38)

```text
Weak:   "The progress key is gone, so the Job failed."
Strong: "A missing key is a cache-miss, not a fact. I read PostgreSQL for the real state and never re-call
        the Provider because Redis forgot a rebuildable projection."

Weak:   "Store the whole progress object as a JSON String."
Strong: "Fields update independently, so a JSON String loses concurrent updates. A Hash updates each field;
        HINCRBY is atomic for the counter."

Weak:   "All Redis commands are atomic, so my update is safe."
Strong: "Per command, yes; across two commands, no. Read-modify-write loses updates and HSET+EXPIRE can
        crash into a permanent key. I use one atomic command or Day41 composition."

Weak:   "Give each tenant its own logical database for isolation."
Strong: "Logical DBs are a namespace, not a security/capacity/failure boundary. I namespace keys in a
        shared keyspace and use real infra/ACLs for isolation."

Weak:   "Enable AOF and Redis becomes the source of truth."
Strong: "AOF only shrinks the loss window; RDB loses post-snapshot writes. Persistence tunes warm-up, never
        ownership — truth stays in PostgreSQL."

Weak:   "Redis is down, so read PostgreSQL for everything."
Strong: "Right direction, but unbounded fallback stampedes the DB. I bound it with Day37 budgets and shed
        or queue excess."

Weak:   "Memory is full — just FLUSHALL."
Strong: "FLUSHALL wipes the shared keyspace across tenants and key classes. I fix the TTL config and clean
        up prefix-scoped keys only."
```

### One-line mental model

```text
Redis is the accelerator, never the authority: small, rebuildable, tenant-scoped, TTL-bounded projections
whose loss triggers a bounded PostgreSQL fallback -- never a Job failure, a Provider re-call, or a FLUSHALL.
```

## Day39 Redis Cache Design and Consistency

Central rule:

```text
PostgreSQL COMMIT = authority.  Redis cache = a rebuildable projection that may be STALE or ABSENT.
A cache hit is not truth; a cache miss is not a Job failure. Judge against the committed PostgreSQL state.
```

### Cache-aside read

```text
GET key -> HIT (return only if the endpoint tolerates staleness)
        -> MISS -> read PostgreSQL (authoritative) -> return -> best-effort SET key TTL(base±jitter)
a cache SET failure NEVER invalidates a correct PostgreSQL response
```

### Invalidation (commit first!)

```text
COMMIT PostgreSQL  ->  THEN invalidate EVERY affected view (job-detail AND recent-completed list)
pre-commit delete race: miss -> read OLD running from PG -> re-cache stale BEFORE commit (fresh TTL) = wrong
baseline = invalidate-after-commit, NOT write-through a guessed final view
```

### Representation / versioning

```text
incompatible change (progress 42 [0-100] -> 0.42 [0-1]) = new versioned key v2 while old/new coexist
additive OPTIONAL field = SAME version
```

### Expiry / stampede

```text
fixed synchronized TTL -> CACHE AVALANCHE (many DISTINCT keys expire together -> all hit PG)
TTL + JITTER          -> spreads expiry (fix for synchronized expiry)
SINGLE-FLIGHT         -> one leader rebuilds ONE hot key; followers wait bounded or take stale value
                         on leader timeout: bounded retry + backoff + jitter, NOT a full fan-out
SWR (stale-while-revalidate) -> tolerant reads only; NEVER for state-changing/sensitive ops
single-flight != a fix for a million distinct keys expiring together (that's jitter)
```

### Fail-open vs fail-closed

```text
GET /jobs/{id}/progress -> fail-OPEN / bounded SWR (a stale number does not corrupt state)
POST /jobs/{id}/cancel  -> fail-CLOSED: PG authorization + GUARDED state transition
                           a cache never authorizes; a PG pre-read is not a substitute for the guarded write
```

### Negative caching / hot key / metrics

```text
penetration (random non-existent IDs) -> SHORT tenant-scoped negative cache; invalidate on creation;
                                         NOT a security control
hot key: a HIT can overload (50k reqs on one key/node); high hit ratio != health
metrics: freshness/correctness -> commit->invalidation delay/failure/backlog, cache age, stale-terminal,
         Redis-vs-PostgreSQL agreement (NOT hit ratio alone)
```

### Invalidation recovery + incident

```text
cache DEL timed out (unknown result): NEVER redo the transition / re-call the Provider
  -> record invalidation INTENT in the Outbox; Relay retries an idempotent DEL; TTL is the backstop
v2 incident (stale v2, Relay timed out): reconcile first (retry invalidation + bounded SWR + protect PG);
  roll back the CACHE contract ONLY on proof of incompatibility; never roll back PG truth or Provider work
```

### Weak vs strong (Day39)

```text
Weak:   "A short TTL keeps the cache in sync."
Strong: "A TTL only bounds staleness; durable changes need post-commit invalidation."

Weak:   "Delete the cache first so nobody reads stale data."
Strong: "Pre-commit delete re-caches the old running state with a fresh TTL. Commit first, then invalidate."

Weak:   "99% hit ratio means the cache is healthy."
Strong: "Hit ratio is efficiency, not truth. I measure cache age, stale-terminal rate, and PG agreement."

Weak:   "Cache says running, so we can cancel."
Strong: "A cache never authorizes a sensitive write. Cancel fails closed on the guarded PostgreSQL write."

Weak:   "Cache delete timed out — resubmit the Job."
Strong: "Never redo the transition or Provider. Record the intent in the Outbox and retry an idempotent DEL."
```

### One-line mental model

```text
Cache consistency is a per-endpoint contract, not a TTL: commit-then-invalidate, TTL+jitter, single-flight/SWR
for hot tolerant reads, fail-closed guarded writes, Outbox+idempotent DEL recovery, and freshness metrics.
```

---

---

Related: [Day38 lesson](../docs/redis/day38-redis-foundations-and-data-structures.md) · [Day39 lesson](../docs/redis/day39-redis-cache-design-and-consistency.md) ·
[Redis acceleration-layer design](../projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md) · [Redis cache consistency design](../projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md)
