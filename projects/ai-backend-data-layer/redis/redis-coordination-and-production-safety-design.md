# Redis Coordination and Production Safety Design

Day41 design artifact for the AI Backend Data Layer. It uses Redis for **narrow, explicitly bounded**
coordination and protection around the Job API and Worker lifecycle — atomic admission control, leases,
stale-owner protection, failure windows, capacity isolation, and security — while **PostgreSQL remains the
durable business authority** (Job/Attempt/Event/Outbox truth) and Provider/notification effects keep their
own stable idempotency identities.

> **Validation status of this whole document.** Everything below is **CONCEPTUAL / STATICALLY REVIEWED**
> only. **RUNTIME NOT RUN. PRODUCTION NOT VALIDATED.** No Redis server, Sentinel, Cluster, managed Redis,
> `redis-cli`, Lua script, `MULTI`/`EXEC`/`WATCH`, ACL, TLS, persistence, eviction, failover, rate limiter,
> FastAPI endpoint, PostgreSQL schema/SQL, Provider, Object Storage, or Worker drain/handoff was run or
> measured. Key names, limits, TTLs, capacities, and refill rates are **static design examples**, not
> measured results or production recommendations. This does **not** promote Redis to business source of
> truth, does **not** claim exactly-once, and does **not** hand-build a broker. Contains **no secrets, real
> connection strings, or client data**.

Related: [Day41 lesson](../../../docs/redis/day41-redis-coordination-and-production-safety.md) ·
[Day40 messaging design](redis-messaging-and-queue-semantics-design.md) ·
[Day39 cache consistency design](redis-cache-consistency-design.md) ·
[Day38 acceleration-layer design](redis-acceleration-layer-design.md) ·
[project README](../README.md)

---

## 1. Ownership recap (the boundary Day41 builds on)

```text
PostgreSQL = AUTHORITATIVE Job/Attempt/Event/Outbox truth; unique constraints + guarded transitions decide it.
Object Storage = large bytes / deterministic result Artifacts (reconciled by stable reference).
Redis (Day41) = a COORDINATION / PROTECTION control only: atomic admission (rate limits) and short leases. It
                may be LOST or ROLLED BACK on eviction/failover and is NOT business truth. The fencing
                GENERATION is NOT a Redis-allocated value -- it is minted durably in a PostgreSQL claim/takeover
                transaction (Section 6/7), precisely because Redis state can roll back.

Redis admission (a consumed rate-limit token) is NOT durable Job success.
A Redis lease grants takeover eligibility; it does NOT stop a paused owner or an in-flight Provider call.
Final correctness = PostgreSQL uniqueness/guarded writes + stable Provider/notification idempotency + Artifact
reconciliation.
```

---

## 2. Rate-limit admission contract

```text
atomic read -> limit decision -> increment -> TTL -> allow/reject     (ONE atomic server-side operation)
Redis admission != durable Job success
PostgreSQL Job + Outbox = durable acceptance truth

WRONG: GET count -> check in app -> SET/INCR      (two Pods both read 59 -> both allow -> race)
WRONG: INCR -> if > limit, DECR to compensate     (a crash/interleave omits or deforms the compensation)
RIGHT: a short Lua script that reads, checks the limit, increments ONLY when allowed, sets/retains TTL,
       and returns allow/reject -- Lua itself is the atomic boundary.
```

The missing property in the two-Pod race is **atomicity**, not necessarily a distributed lock. A lock adds
its own expiry, safe-release, and recovery risks; a rate-limit check/update wants an atomic read-modify-write.

### Lua vs MULTI/EXEC/WATCH (composition boundary)

```text
Lua            : short CONDITIONAL composition (read + compare + conditional INCR + TTL) as ONE atomic step. Correct here.
MULTI/EXEC     : queues commands contiguously, but CANNOT make a client-side decision based on a PRIOR external GET atomic.
WATCH+MULTI/EXEC: an optimistic alternative WITH retry (watch the key; abort+retry on change).
Do NOT put MULTI/EXEC inside Lua -- Lua is already the atomic boundary.
Do NOT wrap a single cache GET in Lua -- one Redis command is already atomic; a script only adds complexity.
```

---

## 3. Rate-limit algorithm decision table

| Algorithm | Burst behaviour | Fairness / smoothness | Cost | Suitable AI Job use |
| --- | --- | --- | --- | --- |
| **Clock-aligned fixed window** | allows a boundary burst (60 at 12:00:59 + 60 at 12:01:00 = 120 in ~1s) | coarse | cheapest (one counter + TTL) | rough, cheap caps where a boundary burst is tolerable |
| **First-write TTL window** (request-anchored) | interval starts at first write; **different semantics** — do **not** call it a clock-aligned fixed minute | request-anchored | cheap | simple per-key throttle; state the anchoring contract explicitly |
| **Sliding window** | prevents the clock-boundary burst; upper bound for **any** continuous interval | smooth / fair | higher storage/implementation | expensive AI Job creation where fairness + smooth admission matter |
| **Token bucket** | permits an occasional burst up to capacity; refill limits long-run average | burst + sustained rate | moderate | sustained ~1 Job/s with an occasional burst of ~10 |

```text
Token-bucket example (STATIC): capacity 10, refill 1/s. Ten tokens consumed, then a request 0.2s later finds
~0 tokens -> REJECTED, and can be given a retry estimate (~0.8s until the next token). Capacity permits the
burst; refill bounds the long-run average.
```

---

## 4. API idempotency boundary

```text
API idempotency key (client-supplied, stable) + PostgreSQL uniqueness (tenant_id, idempotency_key)
  -> INSERT-or-return the SAME Job + the SAME Outbox dispatch intent, then replay the same 202 + job_id.

A timed-out POST retry is de-duplicated at the API by the PostgreSQL UNIQUE boundary -- NOT by inspecting
Attempt/Event/Outbox, because before a Worker starts those may NOT EXIST yet (Outbox proves dispatch intent
only AFTER acceptance).

Separate identities stay independent:
  API idempotency key      -> prevents duplicate durable JOB ACCEPTANCE
  Provider idempotency key  -> prevents duplicate external MODEL EFFECT
  email/delivery identity   -> prevents duplicate NOTIFICATION (e.g. job:{job_id}:notification:completion:v1)

A Redis lock may reduce OPTIONAL duplicate preliminary work, but it is NOT the final authority for Job
identity -- the PostgreSQL unique constraint decides it.
```

---

## 5. Lease safety model (paused-owner timeline)

```text
acquire  : SET lock_key <lease_token> NX PX 30000      (token = opaque ownership id, often UUID-like)
renew    : extend PX only while still the owner (token matches)
release  : ATOMIC compare-and-delete (Lua) -- delete ONLY if the stored token still equals MY token
```

```text
Paused-owner timeline:
  t=0    Worker A acquires a 30s lease (token = A1)
  t=29s  A pauses (GC / stall) mid Provider call
  t=30s  A's lease EXPIRES -> Worker B acquires a NEW lease (token = B1)
  t=..   A resumes, still believing it owns the lease

Lease expiry permits REASSIGNMENT; it does NOT prove A died before external work and does NOT stop a paused A.
Blind `DEL lock_key` after expiry is UNSAFE: A could delete B's lease, letting C enter. Safe release therefore
requires atomic compare-and-delete (Lua): delete only when the stored token still equals the caller's token.
Safe release stops A from deleting B's lease; it does NOT stop A's already-started external Provider call.
```

---

## 6. Fencing model (a different boundary from the lease token)

```text
Lease token   = OPAQUE ownership id (UUID-like), UNORDERED -> good for renew/safe-release, useless for "who is newer".
                It is short-lived Redis COORDINATION and is ALLOWED to be lost/rolled back on eviction/failover.
Fencing generation = a MONOTONICALLY INCREASING ownership generation whose CORRECTNESS MUST NOT depend on
                     rollback-able Redis state.

Allocation source (critical): the fencing generation is advanced and PERSISTED in a PostgreSQL DURABLE
OWNERSHIP TRANSACTION at Claim/takeover -- NOT allocated by a Redis INCR. If Redis assigned it, a failover
could hand a new owner a SMALLER or DUPLICATE generation and the downstream could no longer reliably reject a
stale owner's write. Redis may hold a short lease for coordination; PostgreSQL owns the durable generation.

Why a UUID lease token cannot fence: it has no ordering, so even a cooperating downstream cannot decide which
of two tokens is newer. Fencing requires a monotonic, durably-allocated generation.

Ordinary AI Providers generally do NOT compare the application's fencing generation, so external model effects
still require stable Provider idempotency keys + Artifact reconciliation. Fencing protects a cooperating
DURABLE DOWNSTREAM store (e.g. PostgreSQL) from stale writes; it does not itself de-duplicate a Provider call.
```

Generalized downstream fence rule (a SEPARATE model, not the Job completion predicate): for a generic resource
write to a downstream that has **not** already stored the current owner generation, the downstream accepts a
write only when `last_accepted_fence < incoming_fence`, then persists `incoming_fence`. The Day41 **Job
Complete** design does **not** use this inequality — it uses **equality with the current persisted generation**
(Section 7).

---

## 7. Final PostgreSQL completion guard (extends Day34/Day37)

```text
Claim / takeover (PostgreSQL durable ownership transaction):
  ADVANCE and PERSIST the Job's current_fencing_generation (a new, strictly greater generation), together with
  claim_owner / lease_token / lease_expires_at. This is the ONLY place the generation is minted -- durably, in
  PostgreSQL, never by a rollback-able Redis INCR.

Complete (running -> succeeded) is allowed ONLY when ALL hold:
     job_id
 AND job_status = 'running'
 AND lease_token = the current worker lease token
 AND lease_expires_at > now()
 AND fencing_generation = the current persisted fencing generation      (EQUALITY, not >= and not >)

Why it is safe:
 - Claim/takeover writes a NEW, greater current_fencing_generation.
 - A stale Worker completing with its OLD generation cannot EQUAL the current persisted generation -> rejected.
 - A stale Worker must ALSO satisfy an unexpired lease with the current token -- even if its token has not yet
   been replaced, an expired lease already fails the guard.
 - Providers do NOT understand the fencing generation, so duplicate external side effects are still handled by
   a stable Provider idempotency key + deterministic Artifact reconciliation.

This reuses the repository's existing lease columns (claim_owner / lease_token / lease_expires_at, Day34/Day36)
and adds a durable current_fencing_generation to the same ownership model -- Day41 does NOT invent a conflicting
schema and executed NO SQL.
```

---

## 8. Redis loss / capacity matrix (bounded protection degradation)

| Mechanism | What it loses / does | Effect on a rate-limit counter |
| --- | --- | --- |
| **RDB** | periodic snapshot | loses changes after the last snapshot on restart |
| **AOF** | appends changes; loss window depends on fsync policy | may lose the most recent increments |
| **Async replication** | improves availability | a promoted replica can lack recent primary writes (counter looks lower) |
| **Failover** | promotes a replica | recent counters may be lost -> a temporary protection-degradation window |
| **Eviction** | reclaims memory under `maxmemory` | may reset a rate-limit key -> the next request sees zero and gets a fresh window; repeated eviction continuously weakens protection |
| **TTL** | expiry | intended reset boundary; distinct from unintended eviction |

```text
Redis is acceptable for rate limits EVEN THOUGH a restart/failover/eviction can lose recent counters: it is a
PROTECTION control, not a durable billing ledger. A lost/evicted counter TEMPORARILY allows extra requests and
raises short-term pressure -- monitor it, do NOT misrepresent it as durable quota correctness.

Capacity isolation: high-value coordination/rate-limit state must NOT share an LRU-evictable cache capacity
with ordinary cache data (or the cache can evict the protection). Isolate via separate instances/clusters or
genuinely enforceable resource boundaries, then define memory limits, TTL, eviction policy, alerts, and
acceptable loss windows explicitly.
```

---

## 9. Security matrix

| Control | Requirement |
| --- | --- |
| Network boundary | private-network placement is **necessary but insufficient** on its own |
| Authentication | require auth; no anonymous access |
| ACL — commands | least privilege: only the required command set for a rate-limit client |
| ACL — key prefix | restrict to the `ratelimit:*` prefix; **no** arbitrary key access |
| Dangerous commands | deny `FLUSHALL`, `CONFIG`, `KEYS`, and other destructive/admin authority to app clients |
| TLS | encrypt client-server traffic |
| Audit / monitoring | audit access; monitor for anomalies (below) |

```text
A rate-limit client is limited to its required commands and the ratelimit:* key prefix -- it must NOT hold
arbitrary key access, FLUSHALL, CONFIG, or other destructive authority.
```

### Monitoring signals

```text
Redis-side : used-memory / headroom, eviction rate, keyspace changes, latency / errors / failover /
             replication lag.
App-side   : allow / reject counts, missing-or-reset-key anomalies, fail-closed counts, unexpected Job
             admission spikes (a rate limiter that has silently stopped protecting).
```

### Managed vs self-operated

```text
A managed Redis provider may run infrastructure and some replication/failover operations, but it does NOT
transfer BUSINESS responsibility: the team still owns semantics, capacity/eviction decisions, ACL/TLS use,
monitoring, acceptable data-loss windows, and incident behaviour.
```

---

## 10. Integrated failure runbook

Scenario: Redis fails over and loses some recent rate-limit counters; at the same time Worker A pauses during a
Provider call, its Redis lease expires, and Worker B acquires a new lease for the same Job.

| Concern | Action | Why |
| --- | --- | --- |
| New expensive admission (Redis unavailable) | **fail closed** — return a deliberate retryable response | do not silently remove the cost/capacity protection |
| Worker B holding a fresh lease | **do NOT call the Provider on the lease alone** — reconcile PostgreSQL Job/Attempt/Event/Outbox + stable Provider idempotency + deterministic Artifact | a fresh Redis lease is not proof the work is undone |
| Worker fleet | **do NOT mass-restart** — avoid new Redis-dependent claim/coordination with bounded backoff; drain/preserve running external work, then hand off/reconcile after recovery | a mass restart interrupts in-flight Provider calls |
| Paused Worker A resumes | final PostgreSQL writes guarded by the current lease token + unexpired lease + equality with the current persisted fencing generation (minted durably at takeover); the Provider effect protected by its own idempotency key | a stale owner must not overwrite newer work |
| Lost counters | treat as a temporary **protection-degradation** window; monitor eviction/memory/failover/admission/reject | it is degradation, not durable quota correctness |

```text
Rollback / containment target = NEW admissions and NEW coordination actions dependent on unhealthy Redis.
Do NOT try to "roll back" Provider calls or blindly restart Workers -- external effects require idempotency
and reconciliation, not rollback.
```

---

## Coordination decision summary (one screen)

```text
admission     -> atomic read-modify-write (short Lua); NEVER GET->check->SET, NEVER INCR-then-DECR compensate
algorithm     -> fixed (cheap, boundary burst) / first-write TTL (request-anchored) / sliding (smooth) / token bucket (burst+rate)
admission != success -> Redis token consumed is an ALLOWED attempt; PostgreSQL Job + Outbox = durable acceptance
API idempotency -> client key + PG UNIQUE (tenant_id, idempotency_key); Provider + notification keys are SEPARATE
lease         -> SET NX PX + opaque token; renew while owner; ATOMIC compare-and-delete release (Lua)
lease != stop -> expiry allows takeover; it does NOT stop a paused owner or an in-flight Provider call
fencing       -> MONOTONIC generation; durable downstream rejects older generation; UUID token cannot fence
completion    -> PG guard: running + current token + unexpired lease + fencing_generation = current PERSISTED generation
                 (Day34/37 guard + durable fencing; the generation is minted in a PostgreSQL claim/takeover tx, never Redis)
loss/capacity -> RDB/AOF/replication/failover/eviction can lose counters = temporary protection degradation; isolate from cache
security      -> private net + auth + ACL (command + ratelimit:* prefix) + TLS + deny FLUSHALL/CONFIG + audit/monitor
outage        -> API fail-closed on new expensive admission; no Worker mass-restart; drain + reconcile; monitor degradation
managed       -> infra can be managed; business semantics/capacity/ACL/monitoring/incident stay the team's
```

---

## Future boundaries (not designed here)

```text
Day42  the integrated data ownership + failure + recovery + verification capstone (PostgreSQL + Redis cache/
       messaging/coordination + Object Storage + Outbox + Worker recovery + Provider idempotency + end-to-end
       failure verification)
Phase 4  SQLAlchemy / Alembic; a real rate-limiter / broker / managed Redis is operated, not hand-rebuilt here
```

---

## Validation and evidence classification

```text
CONCEPTUAL / DESIGN     : the rate-limit admission contract, algorithm decision table, API idempotency
                          boundary, lease safety model, fencing model, PostgreSQL completion guard, Redis
                          loss/capacity matrix, security matrix, and integrated failure runbook are design
                          decisions and stated invariants.
STATICALLY REVIEWED     : the Lua/compare-and-delete/SET NX PX and ACL examples are read for shape and naming
                          only.
RUNTIME NOT RUN         : no Redis, Sentinel, Cluster, managed Redis, redis-cli, Lua, MULTI/EXEC, WATCH, ACL,
                          TLS, persistence, or eviction command was executed or measured.
DISPOSABLE Redis/PG     : NOT RUN -- no rate limiter, connection pool, FastAPI endpoint, API idempotency
                          implementation, or PostgreSQL schema/SQL (Job/Attempt/Event/Outbox/lease/fencing)
                          was executed.
FAILOVER/EVICTION/SEC   : NOT RUN -- no RDB/AOF/replication/failover/data-loss measurement, eviction test,
                          ACL/TLS/Secret/certificate, or dangerous-command policy was applied.
APPLICATION INTEGRATION : NOT RUN -- no Provider/Object Storage request, idempotency query, Artifact
                          reconciliation, notification delivery, Worker drain/handoff, or fail-closed endpoint.
PRODUCTION NOT VALIDATED: not deployed; no production accessed; no RPO/RTO, cost, latency, throughput, or
                          data-loss window measured. Every number (60/min, 30s, capacity 10, refill 1/s) is a
                          static design example.
SECURITY                : no secrets, credentials, connection strings, certificates, or client data; all
                          identifiers are placeholders.
NOT CLAIMED             : Redis is NOT promoted to business truth; no exactly-once; no hand-built broker.
```
