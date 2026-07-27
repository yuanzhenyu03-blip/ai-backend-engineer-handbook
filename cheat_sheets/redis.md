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

## Day40 Redis Messaging and Queue Semantics

Central rule:

```text
PostgreSQL = authoritative Job/Attempt/Event/Outbox/Notification truth.
A Redis Stream delivery -- even an XACK -- is TRANSPORT state, NOT business completion.
Redis alone gives NO exactly-once across (Redis ACK + PostgreSQL commit + external Provider call).
```

### List vs Pub/Sub vs Streams

```text
List       persisted FIFO, NO group/PEL/ACK/Claim/redelivery         simple queue (recovery handled elsewhere)
Pub/Sub    live broadcast, NO backlog/ACK/PEL/Claim/replay            loss-tolerant live notifications only
Streams+CG retained backlog* + per-group PEL/ACK/Claim/redelivery     recoverable Job dispatch + notifications
* retained backlog is subject to configured Redis persistence (RDB/AOF) + replication/failover loss windows
  (Day38); persistence reduces loss windows but Redis is NOT durable business truth -- PostgreSQL is authoritative
List gap vs Stream: persistence != a consumer recovery lifecycle
```

### Lifecycle + delivery semantics

```text
XREADGROUP -> entry in the group PEL -> persist a durable decision in PostgreSQL -> XACK (this group only)
crash BEFORE XACK -> entry stays PENDING -> XCLAIM/XAUTOCLAIM -> reconcile durable state -> XACK after decision
at-most-once  = ACK before processing -> crash LOSES the Job (rejected)
at-least-once = process + persist, THEN ACK -> may REDELIVER -> safe with idempotency (chosen)
XACK closes delivery for ONE group; it is not business truth and not other groups' responsibility
```

### Events / groups / ordering / payload

```text
Accept commits job-dispatch Outbox intent -> Relay -> ai:stream:job-dispatch:v1 -> g:job-exec (Worker)
Complete commits job.completed Outbox intent -> Relay -> ai:stream:job-events:v1 -> g:notify-delivery (email)
one group -> ONE consumer per message (competing consumers); separate groups only mean both can RECEIVE an entry
completion email is driven ONLY by a committed job.completed event -- NEVER by an accept/dispatch entry
  (a shared event stream with an explicit event_type is fine if notify-delivery ignores dispatch events)
stream append order = TRANSPORT order; concurrent consumers != business-completion order
  -> PostgreSQL committed Outbox/Event is the source; guarded transitions + idempotency preserve validity
payload = small references (tenant_id, job_id, event_id, event_type, trace); bytes in Object Storage, refs in PostgreSQL
do NOT hand-build a Celery replacement from raw Lists/Streams
```

### Poison messages / trim / notifications

```text
retry LIMIT = capacity-containment policy, NOT an error classifier; a bad immutable contract cannot self-heal
poison path: bounded retry -> durable quarantine/dead-letter -> alert -> repair producer -> controlled replay
  ACK the original ONLY after durable quarantine evidence exists; NEVER silently delete a failed Job message
trim (XTRIM/MAXLEN) = retention/capacity contract; NEVER trim Pending or recovery/quarantine evidence
per-side-effect idempotency: job:{job_id}:notification:completion:v1 (completion/failure/admin are SEPARATE)
  a Job Attempt/Event does NOT prove an email was delivered
```

### Dual-crash recovery

```text
preserve evidence -> inspect PostgreSQL (Job/Attempt/Event/Outbox/Notification) -> reconcile Provider/email by
stable ids -> each group Claims its OWN Pending -> ACK after the recovered durable decision
NEVER: blindly rerun all Jobs / repeat Provider/email / silently delete / aggressively trim Pending evidence
```

### Weak vs strong (Day40)

```text
Weak:   "No ACK means it didn't run; an ACK means the business is done."
Strong: "A Pending entry proves neither. PostgreSQL + reconciliation decide completion; ACK is transport only."

Weak:   "ACK immediately so it isn't redelivered."
Strong: "Early ACK = at-most-once = silent loss. Persist a durable decision first, then XACK (at-least-once)."

Weak:   "Streams give exactly-once."
Strong: "Redis gives at-least-once; exactly-once is engineered with durable state + idempotency + reconciliation."

Weak:   "It hit the retry limit, so the error is permanent."
Strong: "A retry limit is capacity containment, not an error classifier. Classify by evidence/contract semantics."

Weak:   "Memory is tight — trim the stream."
Strong: "Trim is a retention contract. Never trim Pending or recovery/quarantine evidence; it kills replay."
```

### One-line mental model

```text
Redis messaging is recoverable TRANSPORT, not business truth: Streams+Groups for at-least-once dispatch,
persist-then-XACK, per-side-effect idempotency + PostgreSQL reconciliation, quarantine poison, retain before trim.
```

---

## Day41 Redis Coordination and Production Safety

Central rule:

```text
Redis COORDINATES and PROTECTS; PostgreSQL Job/Attempt/Event/Outbox is the DURABLE BUSINESS AUTHORITY.
Redis admission (a consumed rate-limit token) != durable Job success. A lease grants takeover, not a stop.
```

### Atomic rate-limit admission

```text
atomic read -> check limit -> INCR only if allowed -> TTL -> allow/reject   (ONE Lua step = the atomic boundary)
the two-Pod "both read 59" race is missing ATOMICITY, not necessarily a lock
WRONG: GET -> check -> SET/INCR (split across Pods) | INCR-then-DECR compensate (crash/interleave inflates counter)
Lua vs MULTI/EXEC: MULTI/EXEC can't make a decision from a prior external GET atomic; WATCH+MULTI/EXEC = optimistic+retry
do NOT nest MULTI/EXEC in Lua; do NOT wrap a single command (one command is already atomic)
```

### Admission != durable success / API idempotency

```text
Redis admission = an ALLOWED ATTEMPT; do NOT compensate the counter (TTL resets; compensation = 2nd uncertainty boundary)
durable acceptance = INSERT Job(queued) + INSERT Outbox(dispatch intent) -> COMMIT -> 202 + job_id
API idempotency = client key + PG UNIQUE (tenant_id, idempotency_key) -> create-or-return same Job + replay 202
  (Attempt/Event may NOT exist yet -> can't dedup a first POST; Redis lock reduces optional work, NOT the authority)
identities SEPARATE: API key (acceptance) | Provider key (model effect) | notification identity (email)
```

### Rate-limit algorithms

```text
fixed clock-aligned  cheap; BOUNDARY BURST (60 @12:00:59 + 60 @12:01:00 = 120 in ~1s)
first-write TTL      request-anchored interval; DIFFERENT semantics (don't call it a clock-aligned minute)
sliding window       smooth/fair, upper bound for ANY interval; costlier -> expensive AI Job creation
token bucket         burst up to capacity + refill bounds average (cap 10, refill 1/s: 11th req @0.2s -> REJECT)
```

### Lease / safe release / fencing

```text
lease   = SET lock_key <token> NX PX 30000; token = OPAQUE ownership id (UUID-like); LOSABLE Redis coordination; renew while owner
release = ATOMIC compare-and-delete (Lua): delete ONLY if stored token == mine (blind DEL lets old A delete new B's lease)
lease EXPIRY permits TAKEOVER; it does NOT stop a paused owner or an in-flight Provider call
fencing generation = MONOTONIC; correctness must NOT depend on rollback-able Redis -> minted + persisted in a
  PostgreSQL claim/takeover tx (NEVER a Redis INCR, which a failover could hand out smaller/duplicate)
Claim/takeover: advance + persist a NEW strictly-greater current_fencing_generation (durable, PostgreSQL)
Job Complete guard (PG) = job_status='running' AND lease_token=current token AND lease_expires_at > now()
  AND fencing_generation = the current PERSISTED generation   (EQUALITY -- not >= and not >)
generic downstream fence (SEPARATE model, not Job Complete): accept only last_accepted_fence < incoming_fence, then persist it
a UUID token cannot fence (unordered); Providers usually don't compare fencing -> external effects still need
  stable Provider idempotency + Artifact reconciliation
```

### Loss / capacity / security / outage

```text
RDB/AOF/async-replication/failover/eviction can LOSE/RESET counters = TEMPORARY protection degradation (monitor, don't trust as ledger)
a low/missing counter is NOT "under limit"; repeated eviction keeps weakening protection
ISOLATE coordination state from LRU-evictable cache (separate instance/cluster) + define memory/TTL/eviction/alerts/loss-window
security = private net (necessary NOT sufficient) + auth + ACL (command set + ratelimit:* prefix) + TLS + deny FLUSHALL/CONFIG + audit
managed Redis runs infra, NOT business responsibility (team owns semantics/capacity/ACL/monitoring/incident)
OUTAGE: API FAIL-CLOSED on new expensive admission; NO Worker mass-restart; bounded backoff; drain + reconcile durable facts
```

### Weak vs strong (Day41)

```text
Weak:   "Two Pods read 59 -> add a distributed lock."
Strong: "Missing property is atomicity. Use an atomic command / short Lua read-check-INCR-TTL; a lock adds expiry/release risk."

Weak:   "INCR then DECR on reject."
Strong: "A crash between them inflates the counter. Keep check+increment+TTL in one atomic server-side step."

Weak:   "A Redis lock guarantees one Job per POST."
Strong: "PostgreSQL UNIQUE (tenant_id, idempotency_key) decides Job identity; the lock only reduces optional duplicate work."

Weak:   "The lease expired, so the old Worker stopped."
Strong: "Expiry permits takeover; it can't stop a paused owner or its in-flight Provider call. Use a durable PostgreSQL fencing generation (equality guard) + Provider idempotency."

Weak:   "A UUID lease token can fence stale writes."
Strong: "UUIDs are unordered. Fencing needs a monotonic generation the durable downstream compares."

Weak:   "Redis failed over -> the low counter means we're under limit."
Strong: "Lost counters are temporary protection degradation. Monitor; fail closed on new expensive admission."
```

### One-line mental model

```text
Redis coordinates/protects (atomic admission, short leases) but is LOSABLE; the fencing generation is durable in PostgreSQL; PostgreSQL uniqueness +
guarded/fenced writes + stable Provider idempotency + Artifact reconciliation are the durable final authority.
```

---

## Day42 Backend Data Design Capstone (Phase 3 close)

Central rule:

```text
PostgreSQL = single source of DURABLE TRUTH. Object Storage = large BYTES. Redis = TRANSIENT, LOSABLE coordination.
Acceptance, completion, tenant isolation, and audit are decided by guarded/verified/append-only PostgreSQL facts.
```

### Ownership + acceptance + dispatch

```text
durable at 202 = Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent (ONE tx before 202)
  NOT required at 202: Attempt, Event, lease token, fencing generation (appear at claim/takeover)
dispatch = Relay publishes UNPUBLISHED Outbox intents (published_at IS NULL); NOT a scan of `queued`
at-least-once DUPLICATE delivery is normal -> reject the EFFECT with a guarded queued->running (one winner)
  Redis processed markers/counters/leases are LOSABLE, never durable truth
```

### Completion + reconciliation

```text
completion = SHORT guarded tx: Artifact ref + finish Attempt + running->succeeded + job_succeeded Event
guard = running + current lease token + unexpired lease + fencing_generation = current PERSISTED generation (EQUALITY)
Artifact existence ALONE != success -> verify identity/integrity/ownership + fencing + Provider/result evidence
Artifact-first write + PG rollback -> reconcile (Artifact metadata + Provider idempotency); NEVER blind delete/re-call
```

### Degraded modes (by boundary)

```text
Redis unhealthy       -> fail-closed new expensive admission; low counter != quota headroom; no mass restart; bounded backoff; drain
PostgreSQL down        -> do NOT accept new POST /jobs (acceptance atomicity is PG-only); preserve evidence; reconcile after recovery
input Object Storage down / upload unverifiable -> fail-closed THAT admission only (not unrelated endpoints/whole container)
upload verify before admission = tenant ownership + verified state + non-expiry + registered key + hash/size + content-type/scan
```

### Tenant / audit / retention / performance / migration

```text
tenant safety = authenticated tenant predicate + Job ID; composite tenant-aware FKs (job_documents(tenant_id, job_id, document_id))
  a globally-unique job_id still leaks if queried alone; a cache key (job-summary:{tenant_id}:{job_id}:v1) is NOT authorization
audit = APPEND-only Events (never edit); retention = tombstone Artifact ref (key/checksum/created/deleted/policy) + append artifact_expired/deleted
performance = disposable EXPLAIN ANALYZE evidence (representative data/params, actual vs estimated, before/after) != production validation (NOT run here)
fencing migration = Expand->compatible deploy->backfill->validate->switch->contract; drain/upgrade old Workers; lease expiry != a stop
```

### Recovery (integrated)

```text
contain old claims + close legacy-guard-bypass -> no mass restart -> Relay republishes Outbox intent
-> reconcile Job/Attempt/Provider idempotency/Artifact -> guarded atomic completion (or current-owner-only verified next action)
NEVER blind re-call Provider on a fresh lease; NEVER use Artifact existence as ownership proof
```

### One-line mental model

```text
PostgreSQL owns durable truth and atomicity; Object Storage owns verified bytes; Redis coordinates but is losable;
every completion is guarded + fenced, tenants isolated by predicate + composite FKs, audit append-only, recovery reconciles.
```

Validation: CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT VALIDATED (no PostgreSQL/
Redis/Object Storage/Provider/Celery/FastAPI/migration/EXPLAIN ANALYZE executed). SQLAlchemy/Alembic are Phase 4.

---

Related: [Day38 lesson](../docs/redis/day38-redis-foundations-and-data-structures.md) · [Day39 lesson](../docs/redis/day39-redis-cache-design-and-consistency.md) · [Day40 lesson](../docs/redis/day40-redis-messaging-and-queue-semantics.md) · [Day41 lesson](../docs/redis/day41-redis-coordination-and-production-safety.md) · [Day42 capstone lesson](../docs/redis/day42-backend-data-design-capstone.md) ·
[Redis acceleration-layer design](../projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md) · [Redis cache consistency design](../projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md) · [Redis messaging and queue semantics design](../projects/ai-backend-data-layer/redis/redis-messaging-and-queue-semantics-design.md) · [Redis coordination and production safety design](../projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md) · [Day42 capstone design](../projects/ai-backend-data-layer/capstone-backend-data-design.md)
