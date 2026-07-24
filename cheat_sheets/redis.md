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
AOF  append    -> lose writes in the fsync/rewrite window
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

---

Related: [Day38 lesson](../docs/redis/day38-redis-foundations-and-data-structures.md) ·
[Redis acceleration-layer design](../projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md)
