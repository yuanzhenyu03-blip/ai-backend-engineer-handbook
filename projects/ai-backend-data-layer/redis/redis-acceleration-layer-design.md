# Redis Acceleration-Layer Design

Day38 design artifact for the AI Backend Data Layer. It defines Redis as a **bounded, rebuildable
acceleration and transport layer** around the durable truth, without ever making Redis authoritative for the
Job lifecycle.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No Redis server, `redis-cli`, configuration, RDB/AOF
> file, Redis Cluster, workload, benchmark, broker, Worker, PostgreSQL/Object Storage integration, or
> Provider call was run or measured. Key names, TTLs, and eviction settings are **static design examples**,
> not measured results or production recommendations. Contains **no secrets or real connection strings**.

Related: [Day38 lesson](../../../docs/redis/day38-redis-foundations-and-data-structures.md) ·
[project README](../README.md) ·
[Day37 production reliability runbook](../runbooks/postgresql-production-reliability.md)

---

## 1. Ownership model (who owns what)

```text
PostgreSQL app.jobs   = AUTHORITATIVE Job lifecycle / audit truth (Day29-Day37).
Object Storage        = large bytes: source PDFs and Result Artifact bytes.
Redis                 = small, temporary, REBUILDABLE acceleration views + lightweight broker transport.
```

The governing rule: **a missing Redis key is not missing Job truth.** After a TTL expiry, an eviction, a
restart, or a recovery loss, Redis absence cannot decide whether a Job exists, failed, or should call the
Provider again. The authoritative response comes from PostgreSQL; a costly Provider call is never re-issued
because a Redis key is gone.

---

## 2. Keyspace and key contract

```text
Pattern:  ai:tenant:{tenant_id}:<view>:v<N>:<id>
Example:  ai:tenant:{tenant_id}:job-progress:v1:{job_id}
```

- **Tenant namespace is part of every tenant-scoped key.** Omitting `tenant:{tenant_id}` risks returning one
  tenant's cached data to another.
- **Representation versioning (`v<N>`) is for INCOMPATIBLE changes** — a different type, a changed semantic
  contract, or a changed TTL contract. Adding a **backward-compatible optional** Hash field does **not**
  require `v2`.
- **Redis logical databases are not a strong isolation boundary.** They are not a security, capacity, or
  failure-isolation guarantee. Use a shared keyspace plus namespacing; stronger isolation needs explicit
  infrastructure / ACL / capacity policy.

---

## 3. Data-structure decisions (by access pattern)

| Structure | Chosen for | Example | Why (and the trap avoided) |
| --- | --- | --- | --- |
| String | small scalar / counter | a rate-limit request counter with `INCR` | scalar counting; a List would waste one element per request |
| Hash | mutable, named fields | Job-progress view: `stage`, `percent`, `updated_at` | independent field updates; a JSON String read-modify-write can overwrite another Worker's field update |
| List | ordered, duplicates allowed | latest ~20 non-authoritative Job activity records for a UI feed | ordered sequence; not a counter and not authoritative |
| Set | unique membership, unorderd | currently-reporting Worker IDs | uniqueness without order; a **membership view**, NOT ownership authority |
| Sorted Set | unique member + score/order | a tenant's newest completed Jobs: `job_id` member, completion timestamp score | uniqueness + ordering by score, e.g. "recent 100 completions" |

The progress Hash is the canonical example: it fits a full-object read with **independent field updates**,
which a JSON String cannot do safely under concurrency.

---

## 4. TTL and the multi-command boundary

- **TTL means a key is ALLOWED to disappear** — it is a first-class part of the contract, not an
  afterthought.
- **A single Redis command is atomic; a multi-command sequence is not.** `HSET` then `EXPIRE` can crash
  between the two commands and leave an **unintended permanent key**. And two Workers that both read
  `percent = 40` and both write `41` lose one update — use `HINCRBY` for a simple atomic increment.
- Atomic composition of multiple commands (Redis transactions / `MULTI`/`EXEC` / Lua) is a **Day41** future
  boundary and is not designed here.

```text
# STATIC design example only (NOT executed):
#   HSET  ai:tenant:{t}:job-progress:v1:{job} stage extract percent 40 updated_at <ts>
#   EXPIRE ai:tenant:{t}:job-progress:v1:{job} 3600        # a crash between these leaves a permanent key
#   HINCRBY ai:tenant:{t}:job-progress:v1:{job} percent 1  # atomic increment for a single field
```

---

## 5. Memory / eviction as a correctness concern

- `maxmemory` and eviction are **normal production behaviour**, not merely performance tuning.
- **Rebuildable** cache / progress / activity keys are acceptable eviction candidates — they can be rebuilt
  from durable PostgreSQL/Object Storage evidence, or the API returns "real-time progress unavailable."
- **Authoritative lifecycle data must never rely on Redis alone.** Do not mix non-disposable data into the
  same eviction policy without explicit isolation.
- For this disposable keyspace, **allowing eviction is preferable** to treating Redis as indefinite storage.

---

## 6. Persistence boundary (RDB / AOF)

```text
RDB  = compact periodic snapshot; can lose writes since its last successful snapshot.
AOF  = logs writes; its potential loss window depends mainly on the fsync policy (plus OS/disk
       persistence and the failure type) -- still NOT a guarantee of zero lost writes.
       AOF rewrite = log compaction (CPU/I/O/disk ops cost); it is NOT itself a data-loss window.
```

RDB/AOF change Redis **recovery loss windows**; they do **not** grant Redis authoritative Job ownership.
Redis primarily holds an in-memory working set — persistence is a recovery aid, not a source of truth.

---

## 7. Redis outage degradation

```text
Reads:    API reads authoritative lifecycle from PostgreSQL; may report "real-time progress unavailable".
Workers:  existing Workers do NOT mark Jobs failed merely because Redis is unavailable.
Delivery: new broker delivery may be DEFERRED; the durable Outbox intent is retried after recovery.
Protect:  bound the PostgreSQL fallback (pools, timeouts, readiness, rate limits) so an unbounded read
          storm does not move the outage into PostgreSQL (Day37).
```

Broker-transport boundary: if Redis broker publication is unavailable **after** the PostgreSQL Accept
transaction committed `queued Job + Outbox intent`, the API still returns `202 Accepted`; the Relay later
retries the committed Outbox intent. Do **not** fabricate a creation failure or create a duplicate Job.

Broker payload rule: a message carries `job_id`, `tenant_id`, and trace/routing metadata — **not**
authoritative Job truth and **not** large PDF bytes. Workers load Job/Document metadata from PostgreSQL and
large bytes from Object Storage. A 300 MB PDF never belongs in a Redis value or message (memory + network +
persistence/rewrite + replication + recovery + redelivery cost).

---

## 8. Integrated incident: a bad deployment removed progress-key TTLs

```text
Symptom:  progress keys lost their TTL -> memory grew -> normal keys were evicted -> PostgreSQL fallback rose.
```

**Correct containment (in order):**

```text
1. Roll back the TTL CONFIGURATION (stop new permanent progress keys).
   -> Do NOT immediately FLUSHALL (a cache stampede would move the failure to PostgreSQL).
   -> Do NOT merely expand memory (it defers, not fixes).
2. Note: existing no-TTL keys do NOT gain a TTL from the rollback. Identify ONLY the strict progress-key
   prefix and gradually attach a safe TTL or remove those rebuildable keys at a controlled rate.
3. Protect PostgreSQL during cleanup with rate limits and pool monitoring (Day37).
```

**Recovery evidence:**

```text
- memory usage stabilizes / decreases,
- the evicted_keys (forced-eviction) RATE decreases  (note: normal TTL expiration may rise, and is distinct),
- no new no-TTL progress keys appear,
- cache/fallback and API metrics recover,
- PostgreSQL pool waits / connection pressure recover,
- NO Job is marked failed or retried merely because Redis data was absent.
```

---

## Future boundaries (not designed here)

```text
Day39  cache consistency: cache-aside, invalidation, stampede/single-flight, stale reads, fail-open/closed.
Day40  messaging / queue semantics: Lists vs Pub/Sub vs Streams / consumer groups; the broker-payload rule.
Day41  safe multi-command composition: Redis transactions (MULTI/EXEC) / Lua, coordination, full rate limiting.
Day42  the complete data ownership + failure model.
```

Validation classification (whole document):

```text
Conceptual classroom validation:  COMPLETED
Static reasoning review:           COMPLETED
Redis runtime / redis-cli / config: NOT RUN
RDB/AOF / Cluster / workload:       NOT RUN
Broker / Worker / integration:      NOT RUN
Production validation:              NOT VALIDATED
```
