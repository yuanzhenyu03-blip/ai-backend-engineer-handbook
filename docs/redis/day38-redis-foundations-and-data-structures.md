# Lesson 38 — Redis Foundations and Data Structures

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day37 — PostgreSQL Production Reliability

Previous Lesson: [Day37 — PostgreSQL Production Reliability](../postgresql/day37-postgresql-production-reliability.md)

Next Lesson: Day39 — Redis Cache Design and Consistency (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day39 lesson file does not exist yet)

Engineering Artifact: The Day38 Redis acceleration-layer design (`projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md`) — the ownership model, keyspace/versioning contract, data-structure decision table, TTL/eviction and RDB/AOF boundaries, outage degradation, and the missing-TTL incident, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

Redis Cheat Sheet: [cheat_sheets/redis.md](../../cheat_sheets/redis.md)

Redis Interview: [interview/redis.md](../../interview/redis.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on keyspace/data-structure design + disposable-Redis practice: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. State the ownership model — PostgreSQL owns durable Job truth, Object Storage owns large bytes, Redis owns bounded, rebuildable acceleration/transport — and explain why a missing Redis key is not missing Job truth.
2. Fall back to PostgreSQL when a Job-progress key is evicted, never marking the Job failed or re-calling the Provider because Redis lost a key.
3. Choose the right Redis structure by access pattern (String, Hash, List, Set, Sorted Set), and explain why a Hash beats a JSON String for concurrent field updates.
4. Design a tenant-scoped, versioned key contract (`ai:tenant:{tenant_id}:job-progress:v1:{job_id}`) and know when a `v2` is (and is not) required.
5. Treat TTL as a first-class contract, and explain why `HSET` + `EXPIRE` and a two-Worker `percent` update are multi-command races that single-command atomicity does not cover.
6. Treat `maxmemory`/eviction as a correctness concern: rebuildable keys may be evicted; authoritative lifecycle data must never rely on Redis alone.
7. Compare RDB and AOF recovery loss windows and explain that neither grants Redis authoritative ownership.
8. Keep broker messages small (`job_id` + `tenant_id` + trace metadata) and keep large PDFs in Object Storage; return `202` even if broker publication is unavailable after the durable Accept commit.
9. Design bounded Redis-outage degradation that protects PostgreSQL, and solve the missing-TTL incident with a TTL-config rollback and prefix-scoped cleanup rather than `FLUSHALL`.

---

# Why This Matters

Day37 made PostgreSQL a reliable, recoverable source of truth. Day38 adds Redis — and the temptation is to
let a fast in-memory store quietly become authoritative. That is the mistake this lesson exists to prevent.
The opening scenario is exact: a Job-progress key is evicted while PostgreSQL still says the Job is
`running`. If the API treats the missing key as "the Job failed" or re-calls the Provider, it invents a
failure and may pay for a duplicate model call. The correct move is to fall back to PostgreSQL.

Redis is powerful precisely because its state is **allowed to disappear** — TTLs expire, memory pressure
evicts keys, restarts and recovery drop writes. That is a feature for a bounded acceleration layer and a
disaster for a lifecycle of record. So every Redis decision here is really an ownership decision: keep only
small, rebuildable projections and lightweight transport in Redis, keep durable truth in PostgreSQL, keep
large bytes in Object Storage, and make absence trigger a controlled fallback — never a Job failure or a
blind external retry.

Everything in this lesson is design and reasoning. Nothing was executed — no Redis server, `redis-cli`,
config, RDB/AOF, cluster, workload, or integration — and the artifact is labelled that way.

---

# Roadmap Position

```text
Day36  safe schema evolution        Day37  operate PostgreSQL reliably
Day38  Redis as transient acceleration around the durable truth   <-- you are here
Day39  Redis cache design and consistency (cache-aside, invalidation, stampede, fail-open/closed)
Day40  Redis messaging and queue semantics (Lists / Pub-Sub / Streams; the broker-payload rule)
Day41  safe multi-command composition (transactions / Lua), coordination, full rate limiting
Day42  the complete data ownership and failure model
```

Day38 draws the boundary; Day39 designs cache consistency on top of it; Day40 the messaging boundary; Day41
the atomic-composition boundary. Redis transactions/Lua, cache invalidation/stampede, Streams/Pub-Sub, and
full rate-limiting algorithms are all explicitly future work.

---

# Lesson Map

```text
1. Ownership model               -> PostgreSQL truth / Object Storage bytes / Redis acceleration
2. Missing key != missing truth  -> evicted progress key falls back to PostgreSQL
3. Reject Redis-only lifecycle    -> a 24h TTL loses the Job at hour 25
4. Data structure by access pattern -> String / Hash / List / Set / Sorted Set
5. Hash vs JSON String            -> independent field updates vs lost read-modify-write
6. Key contract                   -> tenant namespace + version for incompatible changes
7. Logical DBs are not isolation   -> shared keyspace + namespace
8. TTL is a contract               -> a key is allowed to disappear
9. Multi-command race              -> HSET+EXPIRE crash; two-Worker percent; HINCRBY
10. Memory / eviction              -> rebuildable keys evictable; authority never Redis-only
11. RDB / AOF                      -> loss windows, not ownership
12. Broker payload                 -> job_id + metadata, never a 300 MB PDF
13. Redis outage degradation       -> bounded PostgreSQL fallback; 202 still returned
14. Missing-TTL incident            -> roll back TTL config; no FLUSHALL; recovery signals
```

---

# Core Mental Model

```text
PostgreSQL app.jobs = AUTHORITATIVE Job lifecycle/audit truth.
Object Storage      = large bytes (PDFs, Result Artifacts).
Redis               = small, temporary, REBUILDABLE acceleration views + lightweight broker transport.

A missing Redis key is NOT missing Job truth. TTL expiry / eviction / restart / recovery loss trigger a
CONTROLLED PostgreSQL fallback -- never a Job failure and never a blind Provider re-call.

Pick the structure by ACCESS PATTERN: String (scalar/counter), Hash (named mutable fields),
List (ordered, duplicates), Set (unique membership), Sorted Set (unique + score/order).

A single command is atomic; a multi-command read-modify-write is NOT. TTL is a contract (a key is ALLOWED to
disappear); maxmemory/eviction is a correctness concern; RDB/AOF shrink loss windows but never grant ownership.

Broker messages carry job_id + tenant_id + trace metadata, not truth and not large bytes. If Redis is down,
degrade in a BOUNDED way that protects PostgreSQL; still return 202 after the durable Accept commit.
```

---

# Main Concepts

## Concept 1: The Ownership Model and a Missing Progress Key

Tech Lead Question:

A Job-progress Redis key is evicted while PostgreSQL still says the Job is `running`. What does the API do?

Student Answer:

> "回PostgreSQL 查询，直接判定job失败会造成用户二次发起provider调用。"

Tech Lead Review:

Exactly right, including the business reason. PostgreSQL `app.jobs` is the **authoritative** lifecycle
truth; Object Storage holds the large bytes; Redis holds small, temporary, rebuildable acceleration views.
A missing Redis key is **not** missing Job truth — declaring the Job failed would invent a failure, and
re-calling the Provider could pay for a duplicate, side-effectful model call. The API falls back to
PostgreSQL's lifecycle state, and may rebuild detailed progress **only** from real durable evidence;
otherwise it honestly returns that real-time progress is unavailable.

Engineering Thinking:

Absence in a cache is a cache-miss, not a fact. Route the missing case to the source of truth, never to a
failure verdict or an external retry.

## Concept 2: Reject a Redis-Only Job Lifecycle

Tech Lead Question:

Someone proposes storing the whole Job lifecycle in Redis with a 24-hour TTL. What breaks?

Student Answer:

> "第25小时key实效了，查不到job的记录，也不知道是否成功。"

Tech Lead Review:

Correct. At hour 25 the key expires and the Job's record — and whether it succeeded — is simply gone. TTL
means a key is **allowed to disappear**, which is exactly wrong for a lifecycle of record. Authoritative
Job state must live in PostgreSQL, where it is durable and recoverable (Day37); Redis may hold only a
disposable projection of it.

Engineering Thinking:

If losing the data would lose the truth, the data does not belong in a store whose contract is "this may
vanish."

## Concept 3: Data Structure by Access Pattern

Tech Lead Question:

Design the progress view. Which Redis type, and why not a JSON String?

Student Answer:

> (initially) "不知道" — then, after learning, chose a Hash.

Tech Lead Review:

The honest starting point is fine; the answer is derived from the access pattern. A **Hash** with `stage`,
`percent`, and `updated_at` fits a full-object read **and** independent field updates. A JSON String forces
read-modify-write: two Workers each read the whole object, each change one field, and each write the whole
object back — so one Worker's field update silently overwrites the other's. The Hash lets each field be
updated on its own.

```text
Hash  ai:tenant:{t}:job-progress:v1:{job}  { stage, percent, updated_at }
```

Engineering Thinking:

Choose the structure from how the data is read and written, not from what is convenient. Concurrent field
updates want a Hash, not a serialized blob.

## Concept 4: The Full Structure Palette

Tech Lead Questions (several access patterns):

Recent 100 completed Jobs? Unique reporting Workers? Ordered UI activity? A request counter?

Student Answers:

> (recent completions) "我会选择Sorted Set，因为要求最近100个完成的就不能出现重复的，按时间从新到旧表示需排序。"

> (Worker membership) "应该选set，不希望重复但是也没有要求排序。"

> (ordered UI activity) "选择list。"

> (rate-limit counter) initially chose a List (for TTL/counting), corrected to a String counter.

Tech Lead Review:

The Sorted Set, Set, and List answers are all correct and well-reasoned. A **Sorted Set** gives unique
members with a score for ordering (`job_id` member, completion timestamp score) — perfect for "recent 100
completions." A **Set** gives unique membership without order (currently-reporting Worker IDs — a membership
**view**, not ownership authority). A **List** gives an ordered, duplicate-permitted activity feed. The
counter is the correction: a List can count by length but wastes one element per request; a **String** with
`INCR` is the right scalar counter. (A full rate-limit algorithm is Day41.)

```text
String     small scalar / counter        INCR
Hash       named mutable fields          job-progress view
List       ordered, duplicates allowed   latest ~20 UI activity records
Set        unique membership             reporting Worker IDs (a VIEW, not authority)
Sorted Set unique member + score/order   recent 100 completions (score = completion timestamp)
```

Engineering Thinking:

Five structures, five access patterns. Uniqueness, ordering, and scalar-vs-fields decide the choice — not
habit.

## Concept 5: The Key Contract — Tenant Namespace and Versioning

Tech Lead Questions:

Why does the tenant belong in the key? When do you cut a `v2`?

Student Answers:

> (tenant namespace) "会出现获取到其他租户的缓存信息。"

> (version) "新建 v2 key，因为旧版需要与新版同时运行。"

Tech Lead Review:

The tenant answer is exactly the risk: without `tenant:{tenant_id}` in the key, one tenant's cached data can
be served to another — a cross-tenant exposure. On versioning, the reasoning (old and new must run together)
is right, but the precision matters: cut a **new version for an INCOMPATIBLE change** — a different type, a
changed semantic contract, or a changed TTL contract. Adding a **backward-compatible optional** Hash field
does **not** automatically require `v2`.

```text
ai:tenant:{tenant_id}:job-progress:v1:{job_id}
   ^tenant namespace                ^version = incompatible-change boundary
```

Engineering Thinking:

Put the tenant in every tenant-scoped key, and spend a version only on an incompatible break — not on every
additive field.

## Concept 6: Logical Databases Are Not Isolation

Tech Lead Question:

Should each tenant get its own Redis logical database?

Student Answer:

> "使用同一个database...重复分配Redis database会造成资源浪费。"

Tech Lead Review:

Correct to share. Redis logical databases are **not** a strong security, capacity, or failure-isolation
boundary — they are a lightweight keyspace partition, not a guarantee. Use a **shared keyspace plus
namespacing**; if you need real isolation, that requires explicit infrastructure, ACLs, or a capacity
policy, not a database number.

Engineering Thinking:

A database index is a namespace, not a wall. Do not lean on it for isolation it cannot provide.

## Concept 7: TTL and the Multi-Command Boundary

Tech Lead Question:

You run `HSET` then `EXPIRE`. What happens if the process crashes between them? And if two Workers both bump
`percent`?

Student Answers:

> (HSET then EXPIRE crash) "会导致这条命令一直留在redis中。"

> (two Workers) "不能，因为单命令原子性只能做到一条命令的原子性，而两个work是不同的命令。"

Tech Lead Review:

Both correct. A crash between `HSET` and `EXPIRE` leaves an **unintended permanent key** — the TTL was never
set. And single-command atomicity does not span two commands: two Workers that each read `percent = 40` and
each write `41` lose one update. The fix for a simple counter is `HINCRBY` (one atomic command); atomic
composition of multiple commands (transactions / `MULTI`/`EXEC` / Lua) is **Day41**.

```text
HSET ... ; EXPIRE ...        two commands -> a crash between them leaves a permanent key
read percent; write percent  two commands -> lost update; use HINCRBY (one atomic command)
```

Engineering Thinking:

"Redis commands are atomic" is true per command and false across commands. When correctness spans two
commands, you need an atomic single command or Day41's composition tools.

## Concept 8: Memory and Eviction as a Correctness Concern

Tech Lead Question:

`maxmemory` is reached and eviction starts. Which keys are safe to lose, and which must never be at risk?

Student Answers:

> "B,因为保存的持久化数据，消失以后无法恢复，A可以淘汰，因为可以通过postgresql的持久化数据进行重建。"

> "允许淘汰缓存类 key，因为本身可以重建。"

Tech Lead Review:

Correct. Rebuildable acceleration views (a progress projection, a recent-completions Sorted Set, a cached
read) may be evicted — they can be rebuilt from PostgreSQL. Authoritative lifecycle and audit data must
**never** depend on Redis alone, because eviction can delete it with no recovery path. So `maxmemory` +
eviction policy is not just an ops knob; it is a **correctness** boundary: it decides what Redis is allowed
to forget. The application must treat any rebuildable key as "may be absent" at every read.

Engineering Thinking:

Configure eviction as if it **will** happen, and make sure the only things it can delete are things you can
rebuild.

## Concept 9: RDB and AOF Are Loss Windows, Not Ownership

Tech Lead Question:

How would you configure Redis persistence, and does it make Redis a safe source of truth?

Student Answer:

> "RDB+AOF结合使用...避免使用单个的造成AOF生成的文件过大或者RDB使用的旧的数据。"

Tech Lead Review:

The RDB+AOF combination is a reasonable operational choice, and the student correctly saw the failure mode
of each alone (a stale RDB snapshot; an unbounded AOF file). But the initial belief that "AOF can recover
all lost data" is the misconception to correct: RDB snapshots lose everything written after the last
snapshot, and AOF's potential loss window depends mainly on its fsync policy (plus OS/disk persistence and
the failure type) — so it can still lose the most recent writes and does not guarantee zero loss. AOF rewrite
is log compaction that brings CPU/I/O/disk operational cost; it is not itself an inherent data-loss window.
Persistence **shrinks** the recovery loss window — it does not close it, and it does not make Redis
authoritative. Durable, recoverable ownership stays in PostgreSQL (Day37: replication is not backup;
RPO/RTO are explicit). Redis persistence just makes a warm restart cheaper.

```text
RDB  periodic snapshot   -> lose writes since last snapshot
AOF  append log          -> potential loss depends on fsync policy (rewrite = log compaction / ops cost, NOT a loss window)
both -> smaller recovery loss window, still a loss window, still NOT authority
```

Engineering Thinking:

"We enabled AOF" answers "how fast do we warm up," not "who owns the truth." The answer to the second is
always PostgreSQL.

## Concept 10: The Broker Payload Rule

Tech Lead Question:

A Worker needs a 300 MB PDF a Job produced. What travels through the Redis-backed broker message?

Student Answers:

> "只放job_id，因为完全可以通过job_id找到数据库中的文档地址。"

> "我不支持...大文件会影响CPU的效率。"

Tech Lead Review:

Right — and refusing the large PDF is exactly the instinct to keep. The broker message carries `job_id`
(plus, in this system, `tenant_id` and trace/correlation metadata) — a small reference, not truth and not
bytes. The Worker uses the `job_id` to load Job/Document metadata from PostgreSQL and the large PDF bytes
from Object Storage by reference. Large payloads in broker messages bloat memory, slow every consumer, and
duplicate bytes that already have an owner.

And the availability corollary from earlier days: the API returns `202` after the **durable Accept commit**
in PostgreSQL. If broker publication is momentarily unavailable, that does not undo the Accept — the request
is safely accepted and the enqueue is reconciled (e.g. via the transactional Outbox from Phase 3), rather
than failing the client or losing the Job.

Engineering Thinking:

Messages are pointers. Keep truth in PostgreSQL, bytes in Object Storage, and a small addressed reference on
the wire.

## Concept 11: Bounded Redis-Outage Degradation

Tech Lead Question:

Redis is completely down. What happens to reads that used the progress cache, and how do you protect
PostgreSQL?

Student Answer:

> "不从redis读取进展状态，将traffic直接从postgresql读取持久化数据状态。"

Tech Lead Review:

The fallback direction is right — when Redis is down, progress and cached reads go to PostgreSQL for the
authoritative lifecycle state, and existing Workers never mark Jobs failed just because Redis is
unavailable. The correction added in class is that a raw, unbounded fallback turns a Redis outage into a
PostgreSQL overload (a stampede), so the degradation must be **bounded**: apply the connection budgets,
timeouts, readiness, and rate limits from Day37, and serve a truthful "real-time detail temporarily
unavailable" rather than melting the database. New delivery may be deferred with the durable Outbox intent
retried after recovery. (Full cache-consistency and fail-open vs fail-closed policy is Day39.)

Engineering Thinking:

A cache outage should degrade latency, not correctness — and the fallback must be capacity-aware so it
protects the very database it falls back to.

---

# Common Misconceptions

## Misconception 1: "A missing Redis key means the Job failed"

Wrong. A missing key means the cache lost a rebuildable projection — TTL, eviction, restart, or recovery
loss. The Job's truth is in PostgreSQL. Fall back and read it; never emit a failure verdict or re-call the
Provider because Redis forgot something.

## Misconception 2: "Redis is fast and durable enough to be the source of truth"

Wrong. TTL is a contract that a key may disappear; eviction can delete rebuildable keys; RDB/AOF leave loss
windows. Redis is authoritative for **nothing** in this system — it accelerates and transports around a
PostgreSQL truth and Object-Storage bytes.

## Misconception 3: "Store the whole progress object as a JSON String"

Wrong when fields update independently. A JSON String forces read-modify-write, so concurrent field updates
overwrite each other. A Hash lets `stage`, `percent`, and `updated_at` update on their own; `HINCRBY` bumps
a counter atomically.

## Misconception 4: "All Redis commands are atomic, so my update is safe"

Half true. Each single command is atomic; a read-modify-write across two commands is not, and `HSET` then
`EXPIRE` can crash in the middle and leave a permanent key. Use one atomic command (`INCR`, `HINCRBY`) or
Day41's composition tools (`MULTI`/`EXEC`, Lua).

## Misconception 5: "Give each tenant its own logical database for isolation"

Wrong. Logical databases are a lightweight keyspace partition, not a security, capacity, or failure
boundary. Use a shared keyspace with a tenant namespace in the key; real isolation needs explicit infra and
ACLs.

## Misconception 6: "Enabling AOF makes Redis a safe system of record"

Wrong. AOF shrinks the loss window; it does not close it and does not confer ownership. Persistence changes
warm-up cost, not who owns the truth.

## Misconception 7: "On a Redis outage, just read PostgreSQL for everything"

Right direction, dangerous if unbounded. An uncapped fallback stampedes PostgreSQL. Degrade within Day37
connection/timeout budgets, shed or queue excess, and serve a truthful "temporarily unavailable."

## Misconception 8: "Put the payload in the broker message so the Worker has everything"

Wrong for large bytes. The message carries `job_id` + `tenant_id` + trace metadata; the PDF stays in Object
Storage and truth in PostgreSQL. Fat messages bloat memory and duplicate owned bytes.

---

# Engineering Trade-offs

## Hash vs JSON String for the progress view

A Hash supports independent field updates and partial reads; a JSON String is one blob with atomic
read-modify-write hazards. Choose the Hash when fields change independently or concurrently. Choose a String
only for a genuinely scalar, replace-whole value.

## String counter vs List for counting

A String with `INCR` is O(1), one atomic command, tiny memory. A List can count by length but spends one
element per event and needs trimming. Use the String for counters; use the List when you actually need the
ordered items, not just the count.

## Set vs Sorted Set

A Set gives unique membership with no order at lower cost. A Sorted Set adds a score for ordering and
range/top-N queries at higher cost. Pay for the Sorted Set only when you need ordering or ranking (recent
100 completions); otherwise a Set is enough (reporting Worker IDs).

## TTL length: too short vs too long vs missing

Too short evicts a still-useful projection and forces avoidable PostgreSQL rebuilds. Too long wastes memory
and delays cleanup. Missing (the incident below) leaks keys forever until memory pressure or an outage. TTL
is a deliberate contract per key class, not an afterthought.

## RDB vs AOF

RDB gives compact snapshots and fast restarts but a larger loss window; AOF gives a smaller loss window at
higher write and rewrite cost. The decision tunes restart cost and loss window — never ownership, which
stays in PostgreSQL.

## Bounded fallback vs raw fallback on Redis outage

Raw fallback preserves correctness but can overload PostgreSQL; bounded fallback preserves correctness **and**
protects the database by shedding or queuing excess. Always bound it.

---

# Hands-on Exercises

Design/paper only. Nothing here was executed against a live Redis; treat every snippet as a design artifact.

## Exercise 1: Classify by ownership

For each datum — Job lifecycle state, a 300 MB result PDF, a real-time progress projection, recent-100
completions, currently-reporting Worker IDs, a per-tenant request counter — name the owner (PostgreSQL /
Object Storage / Redis-rebuildable) and, for the Redis ones, the structure and whether eviction is
tolerable. Confirm every Redis datum is rebuildable from an authoritative owner.

## Exercise 2: Write the key contract

Write the full key for a tenant-scoped progress view including tenant namespace and version. Then decide,
for three changes — add an optional Hash field, change `percent` from integer to float semantics, change the
TTL contract — whether each requires a new `v2`. Justify using the incompatible-change rule.

## Exercise 3: Find the multi-command race

Given a Worker that does `HSET progress percent 41` after reading `40`, and a second Worker doing the same,
show the lost update on a timeline. Rewrite it with `HINCRBY`. Then show the `HSET` + `EXPIRE` crash window
and state the resulting bug (a permanent key). Note which fixes need Day41 composition tools.

## Exercise 4: Bound the outage fallback

Redis is down. Sketch the read path's fallback to PostgreSQL with an explicit concurrency/connection budget
and timeout (reuse Day37 numbers as placeholders, not measured values), the shed/queue behaviour past the
budget, and the exact user-facing message. State what stays correct and what merely degrades.

## Exercise 5 (worked): The missing-TTL incident

Scenario:

A deploy shipped a code path that writes progress Hashes **without** `EXPIRE`. Weeks later, Redis memory
climbs toward `maxmemory`, eviction starts touching keys that should have been safe, and progress reads get
noisier. The keys never expired because the TTL was never set.

Student's answer:

> "回滚这次 TTL 配置，因为清空redis会清除正常的缓存key。"

The student correctly chose to roll back the TTL configuration first, reasoning that clearing Redis would
also wipe the normal, healthy cache keys. That reasoning names the exact trap to avoid: `FLUSHALL` (or
`FLUSHDB`) is a **common production trap / unsafe alternative**, not the student's instinct — it would delete
**every** key across the shared keyspace (other tenants, other key classes, healthy cached views), turning a
leak into a self-inflicted outage. The safe path is a TTL-config rollback followed by prefix-scoped cleanup.

Response (design, not executed):

```text
1. Detect     rising memory + eviction on keys that should be safe + progress-key count that only grows.
2. Contain    ship the fix so the write path sets EXPIRE again; stop the leak at the source first.
3. Assess     scan (non-blocking, cursor-based) ONLY the leaked prefix
              ai:tenant:*:job-progress:v1:* to measure blast radius. Never KEYS on a hot server.
4. Clean up   for the leaked keys, set a correct TTL (or delete the ones already safe to drop),
              prefix-scoped -- NEVER FLUSHALL / FLUSHDB.
5. Verify     confirm memory falls, eviction of safe keys stops, and new progress keys carry a TTL.
```

Why not `FLUSHALL`: the keyspace is shared across tenants and key classes (Concept 7). A global flush
destroys unrelated, healthy, still-owned projections and forces mass PostgreSQL rebuilds — a bigger outage
than the leak. Scope every remediation to the offending prefix.

Recovery evidence required before "resolved": memory returns to a normal band; eviction no longer touches
safe keys; a sampled set of newly written progress keys shows a positive TTL; and the leaked-prefix count
stops growing. Only real signals close the incident — no invented metrics. Even at peak leak, no Job truth
was ever at risk — progress Hashes are rebuildable projections of PostgreSQL; the incident was a
memory-hygiene failure in the acceleration layer, not a loss of the system of record.

---

# Relevant Framework Connections

## Redis

Everything in this lesson is Redis, so the production watch items are the invariants themselves: set a
`maxmemory` and a deliberate eviction policy (eviction is a correctness boundary, not a convenience); set a
TTL on every rebuildable key and alert on keys without one; prefer single atomic commands (`INCR`,
`HINCRBY`) over read-modify-write; and never run `KEYS` or `FLUSHALL` on a hot server — use cursor-based
`SCAN` scoped to a prefix.

## PostgreSQL

Redis sits in front of the Day29-37 PostgreSQL truth. The watch item is the boundary: every Redis read must
have a defined PostgreSQL fallback, and that fallback must respect Day37 connection budgets and timeouts so a
cache outage cannot stampede the database. Redis never holds a fact PostgreSQL does not already own.

## Celery / message broker

A Redis-backed broker (Celery, RQ, or a custom queue) must carry only `job_id` + `tenant_id` + trace
metadata. Watch for fat task payloads (large documents, full objects) that bloat broker memory and every
consumer; keep large bytes in Object Storage and pass a reference.

## FastAPI

The API layer is where a missing key becomes a wrong answer. Watch that request handlers translate a Redis
miss into a PostgreSQL read (or a truthful "temporarily unavailable"), never into a `job.failed` response or
a re-submitted Provider call, and that the `202`-after-durable-Accept contract still holds when Redis or the
broker is degraded.

---

# AI Backend Connections

## Progress and status for long model calls

An eight-minute model call needs live progress the client can poll, but that progress is a **projection** of
the durable Job — a Hash the Worker updates and PostgreSQL can rebuild. If it is evicted, the API reports the
PostgreSQL lifecycle state, never a fabricated failure, so the user is never told a running Job died because
a cache forgot it.

## Caching model and retrieval results

Cached embeddings, retrieval hits, or model responses are rebuildable acceleration: they may be evicted and
recomputed, and they must be tenant-namespaced so one tenant never sees another's cached generation. (Cache
consistency, invalidation, and stampede control are Day39.)

## Rate limiting and token-cost control

A per-tenant request or token-budget counter is a String with `INCR` — the small scalar that protects
Provider spend. This lesson sets the counter foundation; the full rate-limit algorithm (windows, atomic
check-and-increment) is Day41.

## Observability

Redis keys are correlated by the same stable `job_id` used across PostgreSQL and logs, so a progress
projection, a durable Job row, and a trace all line up. Memory, eviction rate, and keys-without-TTL are
first-class operational signals — the missing-TTL incident is exactly an observability gap in the
acceleration layer.

---

# English Interview

Vocabulary: acceleration layer, rebuildable projection, cache-miss vs failure, eviction, TTL contract,
keyspace namespace, key versioning, single-command atomicity, read-modify-write, loss window, degradation,
blast radius. Each student answer below is preserved verbatim (the student's own English, unedited),
followed by a stronger model answer.

## Beginner — What is Redis for, and why is it not the source of truth?

Student answer (verbatim):

> "redis can restore temporary cache，also can transit queue message.because redis's data restore memory,it
> can't restore the authoritative source of truth"

Stronger answer:

> "Redis is an in-memory data store used for temporary caching, lightweight message transport, counters, and
> short-lived progress data. It should not be the authoritative source of truth for a Job lifecycle because
> Redis keys can expire, be evicted under memory pressure, or become stale after recovery. PostgreSQL should
> store the durable Job state, while Redis provides rebuildable acceleration."

Assessment: The student named the two roles and the memory-vs-authority point; the model answer sharpens the
reasons (expiry, eviction, recovery staleness).

## Intermediate — A progress key is missing while PostgreSQL says running. What does the API do?

Student answer (verbatim):

> "API should fall back postgresql get the authoritative source of trhtuh,rebuild ,API can't directly return
> faild"

Stronger answer:

> "The API should fall back to PostgreSQL and return the authoritative Job lifecycle state. It may rebuild the
> Redis progress view only if durable evidence is available. It must never mark the Job as failed or retry the
> Provider call just because the Redis key is missing."

Assessment: Correct instinct (fall back, rebuild, do not fail); the model answer adds the "rebuild only from
durable evidence" and "never re-call the Provider" precision.

## Senior — Progress keys shipped without TTL and memory is climbing. What's your plan?

Student answer (verbatim):

> "the plan is that TTLs rollback,contain new Redis progress keys with TTLs,and then cleanup old redis
> progress keys what is not in- flight progress. and then vertificat memory down,eviction decrease,PostgreSQL
> fallback traffic decrease"

Stronger answer:

> "First, I would stop the rollout and roll back the TTL configuration so new progress keys cannot become
> permanent. I would not flush Redis because that could create a cache stampede against PostgreSQL. Next, I
> would identify only the affected progress-key prefix and gradually attach a safe TTL or remove those
> rebuildable keys at a controlled rate. During cleanup, I would protect PostgreSQL with rate limits and pool
> monitoring. I would verify that Redis memory usage stabilizes, the eviction rate decreases, PostgreSQL
> fallback traffic and pool waits return to normal, and no Job lifecycle is marked failed or retried merely
> because Redis data is missing."

Assessment: The student had the full shape (rollback, prefix-scoped cleanup, verify by memory/eviction/
fallback signals); the model answer adds the no-`FLUSHALL`/stampede reasoning and the bounded-cleanup rate.

---

# Mental Model Summary

```text
1.  PostgreSQL owns durable Job truth; Object Storage owns large bytes; Redis owns bounded, rebuildable
    acceleration + lightweight transport.
2.  A missing Redis key is a cache-miss, not missing truth: fall back to PostgreSQL, never fail the Job or
    re-call the Provider.
3.  A lifecycle with a TTL is a lifecycle you will lose; authoritative state never lives only in Redis.
4.  Choose the structure by access pattern: String / Hash / List / Set / Sorted Set.
5.  A Hash beats a JSON String when fields update independently; HINCRBY makes a counter atomic.
6.  Keys are tenant-namespaced and versioned; a new version marks an incompatible change, not an additive
    field.
7.  Logical databases are a namespace, not isolation.
8.  A single command is atomic; a multi-command read-modify-write is not; HSET+EXPIRE has a crash window.
9.  maxmemory/eviction is a correctness boundary: only rebuildable keys may be evictable.
10. RDB/AOF shrink loss windows; they never confer ownership.
11. Broker messages carry job_id + tenant_id + trace metadata, never truth and never large bytes; 202 still
    returns after the durable Accept.
12. A Redis outage degrades within Day37 budgets; the fallback protects PostgreSQL and stays truthful.
13. Fix a missing-TTL leak with a config rollback + prefix-scoped cleanup, never FLUSHALL.

Starting system limitation: the early instinct treats a fast in-memory store as if its presence were proof
and its absence were failure -- reading a missing key as a failed Job, reaching for FLUSHALL, or trusting
AOF as ownership. The evolved model treats Redis presence as a bonus and Redis absence as expected: truth is
asserted only by PostgreSQL, bytes only by Object Storage, and every Redis key is a disposable, rebuildable,
tenant-scoped, TTL-bounded projection whose loss triggers a bounded fallback rather than a wrong verdict.
```

---

# Today's Takeaway

Redis is the accelerator, never the authority. Keep only small, rebuildable, tenant-scoped, TTL-bounded
projections and lightweight transport in it; keep durable truth in PostgreSQL and large bytes in Object
Storage; and make absence trigger a bounded fallback — never a Job failure, a blind Provider re-call, or a
`FLUSHALL`.

Most important mental model: a missing Redis key is a cache-miss, not missing truth. Most important
production risk: a rebuildable key without a TTL (the missing-TTL leak) or an unbounded outage fallback that
stampedes PostgreSQL. Most important connection: Redis accelerates the Day29-37 PostgreSQL truth and must
respect its budgets. Most important interview answer: on a missing progress key, fall back to PostgreSQL and
never re-call the Provider.

Validation status: this lesson is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT
VALIDATED. No Redis server, `redis-cli`, config, command, RDB/AOF file, cluster, or workload was executed;
any figure reused from Day37 is a placeholder, not a measurement. Cache consistency (Day39), messaging
(Day40), and atomic composition/rate limiting (Day41) are future boundaries.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain the core mental model — a missing Redis key is a cache-miss, not missing truth — in plain English?
- [ ] Can I explain why Redis is acceleration only and must never hold an authoritative Job lifecycle?
- [ ] Can I identify the common misconception (a missing key means the Job failed) and correct it?
- [ ] Can I explain the main trade-off — Hash vs JSON String, and bounded vs raw outage fallback?
- [ ] Can I connect Redis to PostgreSQL, a broker, FastAPI, and an AI backend progress/cache/rate-limit path?
- [ ] Can I answer an interview question in English about missing keys, Hash-vs-String, or AOF-vs-ownership?
- [ ] Can I choose String / Hash / List / Set / Sorted Set from an access pattern and defend it?
- [ ] Can I write a tenant-namespaced, versioned key and say when a v2 is required?
- [ ] Can I explain why HSET+EXPIRE and a two-command read-modify-write are not atomic?
- [ ] Can I run the missing-TTL incident end to end without reaching for FLUSHALL?
```

Preparation for Day39 (Redis Cache Design and Consistency): review this lesson's ownership boundary and the
`redis/redis-acceleration-layer-design.md` artifact, then preview cache-aside read/write, invalidation on
durable-state change, stampede/single-flight/stale-while-revalidate, and fail-open vs fail-closed. Keep
Redis transactions/Lua and messaging (Day40-41) and SQLAlchemy/Alembic (Phase 4) out of scope.

---

Engineering Artifact: [projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md](../../projects/ai-backend-data-layer/redis/redis-acceleration-layer-design.md)
