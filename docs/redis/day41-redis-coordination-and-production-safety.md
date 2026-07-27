# Lesson 41 — Redis Coordination and Production Safety

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day40 — Redis Messaging and Queue Semantics

Previous Lesson: [Day40 — Redis Messaging and Queue Semantics](day40-redis-messaging-and-queue-semantics.md)

Next Lesson: [Day42 — Backend Data Design Capstone](day42-backend-data-design-capstone.md)

Engineering Artifact: The Day41 Redis coordination and production-safety design (`projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md`) — the atomic rate-limit admission contract, algorithm decision table, API idempotency boundary, lease safety model, fencing model, the PostgreSQL completion guard, the Redis loss/capacity matrix, the security matrix, and the integrated failure runbook, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

Redis Cheat Sheet: [cheat_sheets/redis.md](../../cheat_sheets/redis.md)

Redis Interview: [interview/redis.md](../../interview/redis.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on admission/lease/fencing + failure-runbook design: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Diagnose a concurrent admission race and explain why the missing property is atomicity, not necessarily a distributed lock.
2. Compose an atomic `read → limit decision → increment → TTL → allow/reject` rate-limit operation in a short Lua script, and reject `GET → check → SET` and `INCR → DECR` compensation.
3. Choose the right Lua vs `MULTI/EXEC` vs `WATCH+MULTI/EXEC` boundary, and avoid wrapping a single command in Lua.
4. Explain why Redis admission is not durable Job success, and keep PostgreSQL Job + Outbox as the durable acceptance truth.
5. Compare clock-aligned fixed window, first-write TTL interval, sliding window, and token bucket by burst, fairness, cost, and use case, including a token-bucket capacity/refill calculation.
6. Design API idempotency with a client key and a PostgreSQL `(tenant_id, idempotency_key)` uniqueness boundary, and keep API, Provider, and notification identities separate.
7. Model a lease (acquire/token/expiry/renew/atomic compare-and-delete release) and explain why expiry permits takeover but does not stop a paused owner or an in-flight Provider call.
8. Distinguish an opaque (losable, Redis) lease token from a monotonic fencing generation that is minted durably in a PostgreSQL claim/takeover transaction, so a durable downstream rejects stale writes.
9. State the final PostgreSQL completion guard (running + current lease token + unexpired lease + `fencing_generation` = the current persisted generation) and why a stale Worker cannot write `succeeded`.
10. Analyze Redis data-loss windows (RDB/AOF/replication/failover/eviction) as bounded protection degradation, and isolate coordination capacity from ordinary cache.
11. Design Redis security (network, auth, ACL command + `ratelimit:*` prefix least privilege, TLS, dangerous-command restriction, audit/monitoring) and explain why managed Redis does not transfer business responsibility.
12. Contain an integrated failover + lease-expiry + paused-Provider incident by failing closed on new admission, not mass-restarting Workers, and reconciling durable facts.

---

# Why This Matters

Day40 gave us recoverable delivery; Day41 is where concurrency, expiry, and failure meet real money. The
opening scene is exact: a tenant is capped at 60 Job creations per minute, two API Pods both read the Redis
count as 59, both decide "allowed," and both create a Job. The cap silently failed — and for an **expensive**
AI Job, every leaked admission is a duplicate model bill. The fix is not "add a lock"; it is **atomicity**: the
read, the limit check, the increment, and the TTL must happen as one indivisible server-side step.

The stakes compound from there. Admit a Job in Redis and then fail the PostgreSQL Accept, and you learn that a
consumed rate-limit token is an *allowed attempt*, not a *created Job* — so you do not try to "give the token
back" across a second uncertain boundary. Hand a Worker a 30-second lease, let it pause at 29 seconds, and a
second Worker takes over while the first is still mid-Provider-call — so a lease alone cannot stop duplicate
external effects, and only a **monotonic fencing generation** plus **PostgreSQL guards** and **stable Provider
idempotency** keep the durable truth and the external effect correct. Lose a counter to a failover or an
eviction and the protection degrades temporarily — which you must **monitor**, not mistake for a durable quota
ledger.

So Day41 is about using Redis for **narrow, bounded coordination and protection** while PostgreSQL stays the
durable business authority. Redis coordinates; it never becomes the source of truth.

Everything here is design and reasoning. Nothing was executed — no Redis, Lua, `MULTI/EXEC`, ACL, TLS,
failover, eviction, rate limiter, FastAPI endpoint, PostgreSQL SQL, Provider, or Object Storage — and the
artifact is labelled that way.

---

# Roadmap Position

```text
Day39 cache consistency     Day40 recoverable delivery + consumer reconciliation
Day41 atomic coordination + production safety   <-- you are here
Day42 integrated data ownership, failure, recovery, and verification (capstone)
```

Knowledge continuity:

```text
Previous knowledge
  Day33/34 guarded transitions, lease ownership (claim_owner / lease_token / lease_expires_at), idempotency
  Day37 the completion guard (running + current token + unexpired lease) and bounded fallback budgets
  Day40 Redis transport is recoverable delivery, NOT final business truth
        |
        v
Current lesson
  atomic admission (rate limits) + Lua composition + admission != success + API idempotency + lease safety +
  fencing generation + PostgreSQL completion guard + loss/capacity + security + failure runbook
        |
        v
Future production usage
  Day42 integrates atomic admission, lease/fencing boundaries, Redis loss windows, security/capacity with
  PostgreSQL, Streams, Object Storage, Outbox, Worker recovery, Provider idempotency, and failure verification
```

Mental models reused by name: the Day34/Day37 completion guard and lease ownership (extended here with a
fencing generation), the Day33 Accept transaction + Transactional Outbox (the durable acceptance truth behind
admission), and the Day40 "Redis is recoverable transport, not truth" boundary (now "Redis coordinates, not
truth").

---

# Lesson Map

```text
1. Concurrent admission race    -> missing property is ATOMICITY, not necessarily a lock
2. Lua conditional composition  -> read+check+INCR+TTL as ONE step; not GET->check->SET, not INCR-then-DECR
3. Admission != durable success -> don't compensate the counter; PostgreSQL Job + Outbox = acceptance truth
4. Algorithm trade-offs         -> fixed / first-write TTL / sliding / token bucket
5. API idempotency              -> client key + PG UNIQUE; API vs Provider vs notification identities
6. Lease, safe release, pause   -> expiry permits takeover; compare-and-delete; expiry can't stop external work
7. Fencing token                -> monotonic generation; downstream rejects stale writes; UUID cannot fence
8. Redis loss / capacity        -> RDB/AOF/replication/failover/eviction = bounded protection degradation; isolate
9. Security + managed           -> network+auth+ACL+TLS+deny dangerous cmds+monitor; managed != responsibility transfer
10. Integrated failure runbook  -> fail-closed admission; no mass restart; drain + reconcile
```

---

# Core Mental Model

```text
Redis COORDINATES and PROTECTS; PostgreSQL Job/Attempt/Event/Outbox is the DURABLE BUSINESS AUTHORITY.

admission     = atomic read-modify-write (ONE Lua step): read -> check limit -> INCR only if allowed -> TTL -> allow/reject
admission != durable Job success: a consumed token is an ALLOWED ATTEMPT; PostgreSQL Job + Outbox = acceptance truth.
API identity  = client idempotency key + PG UNIQUE (tenant_id, idempotency_key); Provider + notification keys are SEPARATE.
lease         = SET NX PX + opaque token; renew while owner; ATOMIC compare-and-delete release.
lease expiry permits TAKEOVER; it does NOT stop a paused owner or an in-flight Provider call.
fencing       = MONOTONIC generation a durable downstream uses to REJECT stale writes; a UUID token cannot fence.
completion    = PostgreSQL guard: running + current lease token + unexpired lease + fencing_generation = the
                current PERSISTED generation (the generation is minted durably at claim/takeover in PostgreSQL, never by Redis).
loss/capacity = RDB/AOF/replication/failover/eviction can lose counters -> TEMPORARY protection degradation (monitor; isolate from cache).
outage        = API fail-closed on new expensive admission; no Worker mass-restart; drain + reconcile durable facts.
```

---

# Main Concepts

## Concept 1: The concurrent admission race — atomicity, not a lock

### Tech Lead Question

A tenant is capped at 60 Jobs/minute. Two API Pods both read the Redis count as 59, both allow, both create a
Job. What property is missing?

### Student Thinking

The student saw two concurrent critical sections and reached for the classic tool — a lock.

### Student Answer

> "缺少并发控制的锁"

### Tech Lead Review

Reasonable instinct, but the missing property is **atomicity**, not necessarily a distributed lock. The bug is
a `read → check → write` split across two Pods: both read 59 before either increments. A rate-limit decision
must be an **atomic read-modify-write** — read, check the limit, increment only when allowed, and set the TTL as
**one** indivisible server-side step. A distributed lock would work but brings its **own** expiry, safe-release,
and recovery risks (the rest of this lesson), so it is the heavier tool for what atomicity already solves.

### Engineering Thinking

Reach for the smallest primitive that removes the race. A concurrent counter wants atomicity; a lock is for
mutual exclusion over a longer critical section, and it is not free.

## Concept 2: Lua for conditional rate-limit composition

### Tech Lead Question

How do you make the check-and-increment atomic? The student proposed `INCR`, then `DECR` on rejection.

### Student Thinking

The student wanted to increment first and undo it if the count turned out to be over the limit; and, on a
related question, recognized a bare `GET` + `MULTI/EXEC` is not atomic as a decision.

### Student Answer

> "先判断是否大于60，如果大于60计数-1返回拒绝"

> "因为不是原子命令，应该将get 与 MULTI/EXEC放在lua脚本中运行"

> (should you wrap a single cache `GET` in Lua?) "不应该"

### Tech Lead Review

The `INCR → check → DECR` shape has crash and interleaving races: a rejected request must **not** rely on a
later compensating decrement (a crash between `INCR` and `DECR` leaves the counter inflated). Keep the check,
the allowed increment, and the TTL in **one atomic server-side operation** — a short **Lua** script that reads
the count, compares it with the limit, increments **only when allowed**, sets/retains the TTL, and returns
allow/reject. Two clarifications the student reached: `MULTI/EXEC` keeps queued commands contiguous but does
**not** make a client-side decision based on a **prior external `GET`** atomic (so `GET` + `MULTI/EXEC` in the
app is still racy — `WATCH + MULTI/EXEC` is the optimistic-with-retry alternative), and you do **not** put
`MULTI/EXEC` inside Lua (Lua is already the atomic boundary). And the "不应该" is right: wrapping a single
`GET` in Lua adds operational complexity for nothing — one Redis command is already atomic.

### Engineering Thinking

Compose only what must be atomic, and no more. Lua is the right tool for a short conditional read-modify-write;
a single command needs no script, and compensation-after-the-fact is not atomicity.

## Concept 3: Admission is not durable Job success

### Tech Lead Question

Redis admitted the request (counter incremented), but the PostgreSQL Accept transaction then failed. Do you roll
the counter back?

### Student Thinking

The student reasoned about what the counter represents and about the TTL reset, and chose not to compensate.

### Student Answer

> "不需要回退。而且每分钟60次还设置了TTL，到时间了就会重新开始一个新的限流计数"

### Tech Lead Review

Correct. The counter represents an **allowed attempt/admission**, not a **successful Job creation**, so there is
nothing to "give back," and the TTL will reset the window anyway. Forcing cross-system quota compensation just
creates a **second** Redis/PostgreSQL uncertainty boundary (did the compensation run? did it crash?). The
durable acceptance truth stays in PostgreSQL's short Accept transaction:
`INSERT Job(status=queued) + INSERT Outbox(dispatch intent) → COMMIT → 202 + job_id`. Redis admission gates
*whether you may try*; PostgreSQL decides *whether a Job exists*.

### Engineering Thinking

Don't reconcile a protection counter against durable state — that couples two systems you were keeping separate.
Let the TTL heal the window and let PostgreSQL own acceptance.

## Concept 4: Rate-limit algorithm trade-offs

### Tech Lead Question

Does a fixed clock-aligned window allow a boundary burst? Which algorithm for expensive AI Job creation, and
which for a tenant needing a steady 1/s with an occasional burst of 10?

### Student Thinking

The student worked the fixed-window boundary case, then chose sliding window for expensive Jobs and token bucket
for the burst-tolerant tenant.

### Student Answer

> (fixed-window boundary) "不会允许，因为12:01:59才会刷新，而这里只是经过了一秒又发了60次"

> (preference) "我更倾向于滑动窗口"

> (burst tenant) "令牌桶"

> (11th request 0.2s after 10 tokens consumed) "无法请求"

### Tech Lead Review

One correction on the boundary case: a clock-aligned fixed window **does** permit a boundary burst — 60 calls at
`12:00:59` and 60 more at `12:01:00` is 120 in about a second, because the window resets at the clock boundary.
(A **first-write TTL** window is request-anchored and has **different** semantics — don't call it a normal
clock-aligned minute.) The **sliding window** the student preferred is exactly right for expensive AI Job
creation: it expresses an upper bound for **any** continuous interval and prevents the clock-boundary burst, at
higher storage/implementation cost. And **token bucket** is the right pick for the burst tenant: with capacity
10 and refill 1/s, the bucket permits an occasional burst of 10 while the refill limits the long-run average —
so the 11th request 0.2s after ten tokens are consumed is **rejected** ("无法请求"), and can be handed a retry
estimate (~0.8s to the next token).

### Engineering Thinking

Pick the algorithm from the traffic shape and the cost of being wrong: fixed for cheap/coarse caps, sliding for
fairness on expensive work, token bucket for sustained-rate-plus-burst.

## Concept 5: API idempotency is not Worker/Provider idempotency

### Tech Lead Question

A `POST /jobs` times out and the client retries. How do you avoid creating two Jobs — check Attempt/Event/Outbox?
And is a Redis lock the authority here?

### Student Thinking

The student proposed reconciling durable Attempt/Event/Outbox facts, and separately thought a Redis lock was
needed to protect concurrent POSTs.

### Student Answer

> "根据数据库持久化事实attempt、event、outbox intent来判断"

> (Redis lock for POST de-duplication) "需要，因为redis锁可以保护多个请求的并发"

### Tech Lead Review

Reconciling durable facts is the right reflex, but **before a Worker begins, Attempt/Event may not exist** — and
Outbox proves dispatch intent only **after** acceptance — so they can't de-duplicate a first-time POST. The API
must accept a **stable client idempotency key** and use a PostgreSQL **uniqueness boundary** such as
`(tenant_id, idempotency_key)` to create-or-return the **same** Job and Outbox intent and replay the same
`202 + job_id`. On the lock: a Redis lock can at most reduce **optional duplicate preliminary work**; it must
**not** be the final correctness authority for Job identity — the **PostgreSQL unique constraint** decides that.
And the three identities stay separate: the **API** idempotency key prevents duplicate durable acceptance, the
**Provider** idempotency key prevents duplicate external model effect, and the **notification/delivery** identity
prevents duplicate email.

### Engineering Thinking

De-duplicate at the boundary that owns the fact: Job identity at the PostgreSQL unique constraint, external
effect at the Provider key, notification at its own delivery identity. A lock is an optimization, never the
authority.

## Concept 6: Lock, lease, safe release, and the paused owner

### Tech Lead Question

Worker A holds a 30-second lease, pauses at 29 seconds, its lease expires, Worker B gets a new lease, and A
resumes. Can a Redis lease alone stop both A and B from calling the Provider? And is a blind `DEL lock_key` after
expiry safe?

### Student Thinking

The student answered the paused-owner case directly, then reasoned about what a blind delete does and what safe
release can and cannot guarantee.

### Student Answer

> (can a lease alone prevent both calling Provider?) "不能"

> (blind DEL after expiry) "会导致下一个work再次进入到A的业务内"

> (can safe release stop the Provider call?) "不能，锁本身只能保证下一个work不会执行当前work中的任务，并不会在当前锁过期后，外部的业务就停止了"

### Tech Lead Review

All correct. Lease **expiry permits reassignment**; it does **not** prove the old Worker died before external
work, and it cannot force a paused A to stop — so a lease alone cannot prevent both A and B from calling the
Provider. A blind `DEL lock_key` after expiry is **unsafe**: old A can delete **new B's** lease, letting a third
Worker C enter (the student's "下一个work再次进入"). **Safe release** therefore requires **atomic
compare-and-delete** — delete only when the stored token still equals the caller's token (a short Lua conditional
composition). The lease token is an **opaque ownership identity** (often UUID-like), useful for renewal and safe
release. And the final point the student nailed: safe release stops A from deleting B's lease, but it does
**not** stop A's already-started external Provider call — that needs Provider idempotency + reconciliation.

### Engineering Thinking

A lease coordinates *who may try next*; it never reaches into an external system to halt in-flight work. Design
release to be token-checked, and design external effects to survive a stale owner.

## Concept 7: The fencing token is a different boundary

### Tech Lead Question

Why isn't the UUID lease token enough to stop a stale write, and how does PostgreSQL reject an older owner?

### Student Thinking

The student first attributed the lease token's insufficiency to the Provider not distinguishing tokens, then
described a fencing comparison in the database.

### Student Answer

> (why UUID lease token is insufficient) "因为下游的provider不能区分lease_token的区别"

> (PostgreSQL fencing) "通过比较fencing token,如果新加入的大于前一个就允许，如果小于就拒绝"

### Tech Lead Review

The student's rule — accept the newer generation, reject the older — is the correct **generalized** downstream
fence rule (`last_accepted_fence < incoming_fence`, then persist `incoming_fence`). Two precisions matter for
correctness. First, the correction to the first answer: it's not only that a Provider can't distinguish tokens —
a **UUID lease token is unordered**, so **even a cooperating downstream store** cannot decide which of two tokens
is newer; fencing needs a **monotonic generation**. Second, and critical: the fencing generation's correctness
**must not depend on rollback-able Redis** — it is advanced and **persisted in a PostgreSQL durable
claim/takeover transaction** (never allocated by a Redis `INCR`, which a failover could hand out smaller or
duplicated). For the **Job Complete** predicate specifically, the guard uses **equality** with the current
persisted generation, not a loose `>=`:

```text
Claim/takeover: advance + persist a NEW, strictly greater current_fencing_generation (PostgreSQL, durable).
Complete allowed only when:
      job_status = 'running'
  AND lease_token = the current worker lease token
  AND lease_expires_at > now()
  AND fencing_generation = the current persisted fencing generation      (EQUALITY)
```

A stale Worker A completing with its **old** generation cannot equal the current persisted generation → rejected;
and even if A's token has not yet been replaced, an expired lease already fails the guard. Ordinary AI Providers
do **not** compare the fencing generation, so **stable Provider idempotency keys + Artifact reconciliation**
remain required for external effects — fencing protects a cooperating **durable downstream**, not the Provider.

### Engineering Thinking

Ordering is the whole point of fencing. An opaque token proves *identity*; a monotonic generation proves
*recency*, which is what a downstream needs to reject stale writes.

## Concept 8: Redis data loss, persistence, and eviction as bounded degradation

### Tech Lead Question

A failover loses recent rate-limit counters; later an eviction resets a key. Does a lower/missing counter mean
the tenant is under limit, and should rate-limit state share capacity with ordinary cache?

### Student Thinking

The student reasoned about why the counter exists, what eviction does to admission, why a replica can lag, and
where to place the state.

### Student Answer

> (counter lost at failover — does a low count mean under-limit?) "不说明，应该是为了防止在这期间无限制调用"

> (eviction risk) "可能多放行一部分请求，造成段短时间请求压力增大"

> (replica missing latest counter) "因为复制的是之前的的限流计数"

> (isolate from ordinary cache) "应该分开放在不同实例，防止缓存挤掉保护数据"

### Tech Lead Review

All correct. Redis is acceptable for rate limits **even though** a restart/failover/eviction can lose recent
counters — it is a **protection control, not a durable billing ledger**. RDB is a periodic snapshot (loses
changes after the last snapshot); AOF appends but its loss window depends on the fsync policy; **asynchronous
replication** improves availability but a promoted replica can lack recent primary writes (the student's
"复制的是之前的的限流计数"). A missing/evicted counter can **temporarily allow additional requests** and raise
short-term pressure, and repeated eviction continuously weakens the protection. So high-value coordination/
rate-limit state must **not** simply share LRU-evictable cache capacity with ordinary cache data — isolate via
separate instances/clusters or genuinely enforceable resource boundaries, then define memory limits, TTL,
eviction policy, alerts, and acceptable loss windows.

### Engineering Thinking

Treat coordination state as a protection control with an explicit, monitored degradation window — and never let
the cache evict the guardrail. Isolation of capacity and failure semantics is a design decision, not a default.

## Concept 9: Security, isolation, ACL, and managed responsibility

### Tech Lead Question

Is putting Redis on a private network enough? What command/key scope should a rate-limit client have, and does
managed Redis remove your responsibility?

### Student Thinking

The student judged private-network placement insufficient, argued for tightly scoped ACLs, and held that managed
Redis still needs the team's configuration.

### Student Answer

> (private-network Redis security) "不能"

> (ACL scope) "不能，对待高风险命令应该严格限制，只能在规定范围的key前缀进行读写权限"

> (managed Redis responsibility) "不能,因为实际业务还是需要自运维进行配置"

### Tech Lead Review

Correct throughout. Private-network placement is **necessary but insufficient** — layer network restriction,
authentication, ACLs, TLS, dangerous-command restrictions, auditing, and monitoring. A rate-limit client should
be limited to its **required command set** and the **`ratelimit:*` key prefix**, with **no** arbitrary key
access, `FLUSHALL`, `CONFIG`, or other destructive authority. And managed Redis does **not** transfer business
responsibility: a provider may run infrastructure and some replication/failover operations, but the **team**
still owns semantics, capacity/eviction decisions, ACL/TLS use, monitoring, acceptable data-loss windows, and
incident behaviour. Monitor Redis-side signals (used-memory/headroom, eviction, keyspace changes, latency/
errors/failover/replication lag) and app-side signals (allow/reject counts, missing/reset-key anomalies,
fail-closed counts, unexpected admission spikes).

### Engineering Thinking

Security is layered and least-privilege; "managed" outsources operations, not accountability for correctness and
capacity.

## Concept 10: Integrated failover + lease + Provider incident

### Tech Lead Question

Redis fails over and loses recent counters; at the same moment Worker A pauses mid-Provider-call, its lease
expires, and Worker B gets a new lease for the same Job. Does B call the Provider? What do the API and the Worker
fleet do while Redis is unhealthy?

### Student Thinking

The student reasoned from durable facts and idempotency for B, chose fail-closed for expensive admission, refused
a mass restart, and named the monitoring signals.

### Student Answer

> (does B call Provider on a fresh lease?) "不能，要先根据数据库持久化事实结合idempotency进行判断是否要再次调用，以及如果A恢复后可能会继续执行业务"

> (expensive creation while Redis unavailable) "fail-closed，因为主要是post一类的请求，需要修改持久化数据状态。"

> (mass-restart Workers?) "不会，因为还是要与数据库持久化事实结合idemotency key进行判断"

> (monitoring) "eviction、以及是否限流器失去了作用，请求增大"

### Tech Lead Review

Correct on every part. Worker B must **not** call the Provider **solely** because it acquired a fresh Redis
lease — it must reconcile PostgreSQL Job/Attempt/Event/Outbox facts, the stable Provider idempotency key, and the
deterministic Artifact state, and it must account for a resumed A. During Redis unavailability the API should
**fail closed** for new expensive Job admission (a deliberate retryable response) rather than silently removing
the cost/capacity protection. The Worker fleet should **not** batch-restart (that interrupts in-flight Provider
calls); instead avoid new Redis-dependent claim/coordination with **bounded backoff**, preserve/drain running
external work, and hand off/reconcile after recovery. Lost counters are a **temporary protection-degradation**
window to be **monitored** (eviction, and "限流器失去了作用" — admission volume rising), not misrepresented as
durable quota correctness. The containment target is **new admissions and new coordination** that depend on
unhealthy Redis — you do **not** "roll back" Provider calls or blindly restart Workers.

### Engineering Thinking

Contain by stopping *new* dependence on the unhealthy control, not by undoing external effects. Reconcile durable
facts and idempotency; drain rather than restart.

---

# Common Misconceptions

Missing lock vs missing atomicity

❌ "Two Pods both read 59 — we need a distributed lock."
✅ The missing property is atomic read-modify-write. Prefer an atomic command or a short Lua conditional; a
distributed lock adds its own expiry, safe-release, and recovery problems.

Why beginners think this: concurrent critical sections look like a lock problem.
How to remember: a counter needs atomicity; a lock is the heavier tool.

Compensating decrement

❌ "`INCR`, and if it's over the limit, `DECR` and reject."
✅ A crash or interleave can omit/deform the compensation. Keep check + allowed increment + TTL in one atomic
server-side operation.

Why beginners think this: undoing the increment feels symmetric.
How to remember: a rejected request must not depend on a later decrement.

Fixed-window semantics

❌ "A request-set TTL is just the normal one-minute fixed window."
✅ A clock-aligned fixed window resets at time boundaries and permits boundary bursts; a first-write TTL is a
request-anchored interval with distinct semantics. State the contract.

Why beginners think this: both use a ~60s TTL.
How to remember: clock-aligned resets on the clock; first-write resets from the first write.

API retry facts vs Worker facts

❌ "De-duplicate a timed-out POST by checking Attempt/Event/Outbox."
✅ Before a Worker starts, those may not exist. Use a client idempotency key + PostgreSQL uniqueness to
create-or-return one Job; Outbox proves dispatch intent only after acceptance.

Why beginners think this: durable facts feel authoritative.
How to remember: no Worker yet means no Attempt/Event yet.

Redis lock as final dedup authority

❌ "A Redis lock protects concurrent POSTs from creating duplicate Jobs."
✅ The PostgreSQL unique constraint is the durable final authority; a Redis lock can at most reduce optional
duplicate preliminary work.

Why beginners think this: a lock feels like it guarantees single execution.
How to remember: identity is decided by the DB constraint, not the lock.

Lease token stops external work

❌ "An expired/different lease token stops the old Worker's Provider call."
✅ Lease expiry permits takeover but does not stop a paused Worker or an already-started Provider call.

Why beginners think this: losing the lease sounds like losing the ability to act.
How to remember: a lease coordinates the next owner; it can't reach into the Provider.

UUID token vs fencing token

❌ "A UUID lease token can act as a fencing token."
✅ UUID tokens are unordered and can't express stale-vs-new even to a cooperating downstream. Fencing must
increase monotonically.

Why beginners think this: both are "the token."
How to remember: fencing needs order; a UUID has none.

Fencing vs Provider idempotency

❌ "Fencing also stops duplicate Provider calls."
✅ Fencing protects a cooperating durable downstream that compares generations. An ordinary Provider needs its
own stable idempotency key + Artifact reconciliation.

Why beginners think this: both prevent "bad" repeated effects.
How to remember: fencing guards the DB; idempotency guards the Provider.

Managed Redis removes responsibility

❌ "Managed Redis means the provider owns correctness."
✅ Infrastructure operation can be managed, but the team still owns semantics, capacity/eviction, ACL/TLS,
monitoring, loss windows, and incident behaviour.

Why beginners think this: "managed" sounds like "handled."
How to remember: managed infra ≠ transferred accountability.

Redis persistence causes memory growth

❌ "Enabling persistence makes Redis use more memory."
✅ Redis is memory-resident; persistence adds disk/write/recovery costs. TTL, memory budget, and eviction policy
define capacity and protection-degradation behaviour.

Why beginners think this: persistence sounds like "keep more in memory."
How to remember: persistence is a disk/recovery cost, not a memory cost.

---

# Engineering Trade-offs

## Atomic command / Lua vs a distributed lock

An atomic command or short Lua removes a counter race cheaply with no ownership lifecycle. A distributed lock
generalizes to longer critical sections but adds acquisition, expiry, safe-release, and recovery risk. Use
atomicity for a rate-limit counter; reserve locks for genuine mutual exclusion and expect to manage their
failure modes.

## Lua vs MULTI/EXEC vs WATCH+MULTI/EXEC

Lua runs a short conditional composition as one atomic step — ideal for read+check+increment+TTL. `MULTI/EXEC`
batches commands but can't make a decision from a prior external `GET` atomic. `WATCH+MULTI/EXEC` is optimistic
with retry, better under low contention where you want to avoid scripting. Choose Lua for conditional
composition; don't nest `MULTI/EXEC` in Lua or wrap a single command in a script.

## Fixed vs first-write TTL vs sliding vs token bucket

Fixed windows are cheapest but allow boundary bursts; first-write TTL is request-anchored with different
semantics; sliding windows are smooth and fair but costlier; token buckets allow controlled bursts with a bounded
average. Match the algorithm to traffic shape and the cost of a leak — expensive AI Jobs favor sliding or token
bucket over a cheap fixed window.

## Compensating admission vs letting the TTL heal

Compensating the counter after a failed Accept adds a second cross-system uncertainty boundary; letting the TTL
reset the window keeps the systems decoupled at the cost of a slightly looser count. Prefer decoupling — the
counter is a protection control, not an exact ledger.

## Lease + fencing + PostgreSQL guard vs a lease alone

A lease alone is simple but cannot stop a paused owner or a stale write. Adding a monotonic fencing generation
and the PostgreSQL completion guard makes stale writes rejectable, at the cost of a monotonic generation and a
guarded write path. For anything that mutates durable Job state, the guarded path is mandatory; the lease is
only coordination.

## Shared vs isolated Redis capacity

Sharing one Redis for cache and coordination is cheaper to run but lets LRU eviction drop the guardrail under
cache pressure. Isolating coordination state (separate instance/cluster or enforceable boundary) costs more
infrastructure but protects the protection. Isolate high-value coordination state from ordinary evictable cache.

## Fail-closed vs fail-open on a Redis outage

Failing closed on new expensive admission protects cost and capacity but rejects some legitimate traffic during
the outage; failing open preserves availability but removes the guardrail entirely. For expensive, state-changing
admission, fail closed with a deliberate retryable response and monitor the degradation.

---

# Hands-on Exercises

Design/paper only. Nothing here was executed against a live Redis or PostgreSQL; treat every snippet as a
design artifact. Every number (60/min, 30s, capacity 10, refill 1/s) is a static design example, not a
measurement.

### Exercise 1: Diagnose the two-Pod admission race

Question: two API Pods both read the rate count as 59 and both admit. Name the missing property and the fix.

Think First: is the problem mutual exclusion or an indivisible read-modify-write?

Expected Output: the missing property is atomicity; fix with an atomic `read → check → INCR (if allowed) → TTL →
allow/reject`, not a `GET → check → SET` split.

Explanation: both Pods read the stale 59 before either increments.

Follow-up Question: why is a distributed lock the heavier tool here?

### Exercise 2: Write the atomic admission operation

Question: express the rate-limit decision as one atomic server-side step and say why `INCR → DECR` compensation
is wrong.

Expected Output:

```text
Lua (atomic): read count -> if count < limit then INCR + (set TTL if new) -> allow; else -> reject
NOT: INCR then DECR-on-reject (a crash between them leaves the counter inflated)
```

Explanation: a rejected request must not depend on a later compensating decrement.

Follow-up Question: where does `WATCH+MULTI/EXEC` fit, and why not nest `MULTI/EXEC` in Lua?

### Exercise 3: Compensate admission after a failed Accept?

Question: Redis admitted, PostgreSQL Accept failed. Roll back the counter?

Expected Output: no — the counter is an allowed attempt, not a created Job; the TTL resets the window;
compensation adds a second uncertainty boundary. PostgreSQL Job + Outbox is the acceptance truth.

Explanation: don't couple a protection control to durable state.

Follow-up Question: what exactly commits in the Accept transaction?

### Exercise 4: Compare the four algorithms

Question: fill burst / fairness / cost / use case for clock-aligned fixed, first-write TTL, sliding, token
bucket.

Expected Output: fixed = boundary burst, cheap; first-write TTL = request-anchored, distinct semantics; sliding =
smooth/fair, costlier (expensive AI Jobs); token bucket = burst up to capacity + bounded average.

Explanation: the fixed window's `12:00:59` + `12:01:00` = 120 burst is the key hazard.

Follow-up Question: which did the student pick for expensive Job creation, and why?

### Exercise 5: Token-bucket calculation

Question: capacity 10, refill 1/s. Ten tokens consumed; a request arrives 0.2s later. Allowed?

Expected Output: rejected (~0 tokens available); give a retry estimate (~0.8s to the next token). Capacity permits
the burst; refill bounds the average.

Explanation: refill is continuous but 0.2s < 1s yields no whole token.

Follow-up Question: how would you communicate the retry estimate to the client?

### Exercise 6: API idempotency around `(tenant_id, idempotency_key)`

Question: design create-or-return for a timed-out POST retry.

Expected Output: client sends a stable idempotency key; a PostgreSQL UNIQUE `(tenant_id, idempotency_key)`
creates-or-returns the same Job + Outbox intent and replays the same `202 + job_id`; API, Provider, and
notification identities stay separate.

Explanation: Attempt/Event may not exist yet; the DB constraint is the authority.

Follow-up Question: what can a Redis lock legitimately do here, and what can it not?

### Exercise 7: Paused-owner lease timeline

Question: A holds a 30s lease, pauses at 29s, expires, B takes over, A resumes. What can a lease guarantee?

Expected Output: expiry permits takeover only; it cannot stop paused A or A's in-flight Provider call; a lease
alone can't prevent both A and B calling the Provider.

Explanation: a lease coordinates the next owner, not external work.

Follow-up Question: what protects the durable write and the external effect respectively?

### Exercise 8: Compare-and-delete safe release

Question: why is `DEL lock_key` after expiry unsafe, and what replaces it?

Expected Output: old A could delete new B's lease (letting C enter); replace with an atomic compare-and-delete
(Lua) that deletes only when the stored token equals the caller's token.

Explanation: release must be token-checked.

Follow-up Question: does safe release stop A's Provider call? (No.)

### Exercise 9: Opaque lease token vs monotonic fencing token

Question: why can't a UUID lease token fence, and what does?

Expected Output: UUIDs are unordered, so even a cooperating downstream can't tell newer from older; a monotonic
fencing generation, recorded and compared by the durable downstream, rejects stale writes.

Explanation: fencing needs order; identity is not recency.

Follow-up Question: do ordinary Providers compare fencing tokens?

### Exercise 10: Protect PostgreSQL completion from a stale owner

Question: write the completion guard.

Expected Output: `running` + current lease token + `lease_expires_at > now()` + `fencing_generation` = the
current persisted fencing generation (equality); a stale Worker's `succeeded` is rejected because its old
generation cannot equal the current one. The generation is minted durably at claim/takeover in PostgreSQL.

Explanation: reuses the Day34/Day37 guard plus a durably-allocated fencing generation (not a Redis value).

Follow-up Question: which existing lease columns does this reuse, and where is the generation advanced?

### Exercise 11: Rate-limit loss during RDB/AOF/replication/failover

Question: what happens to a counter across each mechanism, and what does a low count mean?

Expected Output: RDB loses post-snapshot changes; AOF loss depends on fsync; a promoted replica can lack recent
writes; a low/missing counter is not "under limit" — it's degraded protection to monitor.

Explanation: Redis is a protection control, not a durable ledger.

Follow-up Question: how do you bound and monitor the degradation window?

### Exercise 12: Eviction and cache/coordination isolation

Question: an eviction resets a rate-limit key. Effect, and how to prevent it structurally?

Expected Output: the next request sees zero and gets a fresh window (extra requests, short-term pressure);
isolate coordination state from LRU-evictable cache via separate instances/enforceable boundaries with explicit
memory/TTL/eviction/alerts.

Explanation: don't let the cache evict the guardrail.

Follow-up Question: what policy fields must you define for the coordination instance?

### Exercise 13: Rate-limit ACL scope

Question: design the ACL for a rate-limit client.

Expected Output: least-privilege command set + `ratelimit:*` key prefix only; deny arbitrary keys, `FLUSHALL`,
`CONFIG`, and destructive/admin commands; add auth + TLS.

Explanation: a compromised client should reach nothing beyond its prefix.

Follow-up Question: why is private-network placement necessary but insufficient?

### Exercise 14: Monitoring signals for protection degradation

Question: list Redis-side and app-side signals.

Expected Output: Redis: used-memory/headroom, eviction, keyspace changes, latency/errors/failover/replication
lag. App: allow/reject counts, missing/reset-key anomalies, fail-closed counts, unexpected admission spikes.

Explanation: a silently-broken limiter shows up as rising admission and resets.

Follow-up Question: which signal reveals a limiter that has stopped protecting?

### Exercise 15: Integrated failover + lease + Provider incident (reusable artifact)

Question: Redis fails over and loses counters; A pauses mid-Provider-call, its lease expires, B gets a new lease.
Contain it.

Expected Output: API fail-closed on new expensive admission; no Worker mass-restart; bounded backoff on new
Redis-dependent actions; drain/preserve running work; B reconciles PostgreSQL facts + Provider idempotency +
Artifact before any call; guard final writes by ownership + fencing; treat lost counters as monitored
degradation. This maps to the artifact's failure runbook.

Explanation: contain new dependence on unhealthy Redis; reconcile external effects, don't roll them back.

Follow-up Question: what are the containment targets, and what is explicitly not a target?

---

# Relevant Framework Connections

## PostgreSQL

PostgreSQL is the durable authority behind every Redis coordination control: the Accept transaction (Job +
Outbox) is the acceptance truth, `(tenant_id, idempotency_key)` uniqueness decides Job identity, and the guarded
completion write (running + current lease token + unexpired lease + `fencing_generation` = the current persisted generation, minted durably at claim/takeover) rejects stale-owner writes.
Watch that admission, locks, and leases never become the authority for identity or completion.

## Redis (atomic commands, Lua, MULTI/EXEC/WATCH)

Redis provides the atomic primitives — single commands, short Lua conditional composition, and
`MULTI/EXEC`/`WATCH` as alternatives — plus leases via `SET NX PX` and compare-and-delete release. Watch that
composition is only as wide as it must be (no `MULTI/EXEC` inside Lua, no script around a single command) and
that coordination keys are ACL- and capacity-isolated.

## FastAPI / API layer

`POST /jobs` is where admission, idempotency, and fail-closed behaviour live: the handler runs the atomic
admission, honors the client idempotency key against the PostgreSQL constraint, and fails closed on new expensive
admission when Redis is unhealthy. Watch that a rejected admission returns a deliberate retryable response, not a
silent bypass.

## Worker processes and Object Storage

Workers acquire/renew/release leases and, on takeover or resume, reconcile against PostgreSQL and the
deterministic Artifact in Object Storage before repeating external work. Watch that a fresh lease never triggers
a Provider call on its own and that running work is drained, not mass-restarted, during a Redis outage.

## Managed Redis / Streams (Day40)

Managed Redis runs infrastructure and some failover, but not business semantics; Day40 Streams remain recoverable
transport, not truth. Watch that "managed" is not read as "correctness handled," and that coordination reuses the
same durable-truth boundary as messaging.

---

# AI Backend Connections

## Expensive Job admission and duplicate model cost

The rate limiter exists because AI Job creation is expensive: a leaked admission from a non-atomic counter is a
duplicate model bill. Atomic admission and the right algorithm (sliding/token bucket for expensive work) protect
cost and tenant fairness, while PostgreSQL decides whether a Job actually exists.

## Long-running Provider calls under lease expiry

An eight-minute Provider call can outlive a 30-second lease, so a paused Worker's call may still be in flight when
a new owner appears. Stable Provider idempotency keys + Artifact reconciliation (not the lease) prevent a
duplicate model effect, and the PostgreSQL fencing/ownership guard prevents a stale `succeeded`.

## Tenant fairness and abuse/capacity protection

Per-tenant rate limits protect shared capacity from a noisy or abusive tenant; a token bucket lets a tenant burst
occasionally while bounding the long-run average. When Redis is unhealthy, failing closed on new expensive
admission protects every other tenant's capacity and cost.

## Durable business facts vs coordination state

Job/Attempt/Event/Outbox in PostgreSQL and the deterministic Artifact in Object Storage are the business facts;
Redis admission counters and short leases are coordination that can be lost or rolled back on failover/eviction;
the fencing **generation**, by contrast, is a **durable PostgreSQL** value minted at claim/takeover precisely so
it survives a Redis failover. The reconciliation after any incident reads the durable facts, never the losable
Redis coordination state.

---

# English Interview

## Key Vocabulary

atomic read-modify-write, Lua script, `MULTI/EXEC`, `WATCH`, rate limit, fixed / sliding window, token bucket,
admission, idempotency key, unique constraint, lease, lease token, safe release, compare-and-delete, fencing
token, monotonic generation, stale write, eviction, failover, replication lag, fail-closed, ACL, TLS,
protection degradation.

## Useful Expressions

"The missing property is atomicity, not a lock." · "Admission is not durable success." · "A lease permits
takeover; it can't stop a paused owner." · "A UUID token can't fence — fencing needs order." · "Fail closed on
new expensive admission; reconcile, don't roll back."

## Beginner Question — Why can `GET → check → INCR` create a race in a Redis rate limiter, and what is safer?

Student answer (verbatim):

> because these comman in a same Atomicity transaction ,use lua script instead of comman.

Correction and strong spoken answer:

> "`GET`, checking the value, and `INCR` are separate operations. Two API instances can read the same old value
> before either instance increments it, so both may allow the request. A safer approach is to use a short Lua
> script that reads, checks, increments, and sets the TTL atomically."

Assessment: the student correctly reached for Lua; the strong answer names *why* — the read/check/increment are
separate, so two instances read the same stale value.

## Intermediate Question — Lease token vs fencing token, and why a lease token alone isn't enough for a paused worker?

Student answer (verbatim):

> lease token just avoid a worker running stop,lease token expire.other worker continue  working.the worker wake up continue running.lease token can't continue beacuse lease token different.but the real bussiness can't stop.fencing token store database,the next fencing token must more than before fencing token

Correction and strong spoken answer:

> "A lease token is an opaque ownership identifier. It helps a worker renew or safely release its current lease,
> but it cannot stop a paused worker after the lease expires. A fencing token is a monotonically increasing
> ownership generation. The downstream durable store records the newest token and rejects writes from older
> tokens, so a stale worker cannot overwrite newer work. External providers may not support fencing, so they
> still need stable idempotency keys and reconciliation."

Assessment: the student had the core insight (lease can't stop the real business; fencing is stored and
monotonic); the strong answer adds the opaque-vs-ordered distinction and the Provider-idempotency boundary.

## Senior Question — Redis fails over and loses counters; A pauses mid-Provider-call, its lease expires, B gets a new lease. Contain it.

Student answer (verbatim):

> use the durable database truth,such as event\attempt\oubox intex and idepmotency key reconcil artifact.

Correction and strong spoken answer:

> "First, I would fail closed for new expensive Job admission while the Redis rate limiter is unavailable, and I
> would not restart all workers because that could interrupt in-flight Provider calls. After failover, I would
> treat lost rate-limit counters as a temporary protection degradation and monitor evictions, memory pressure,
> failover, admission volume, and reject rate. Worker B must not call the Provider only because it acquired a new
> Redis lease. It should reconcile PostgreSQL durable facts such as the Job, Attempt, Event, and Outbox records,
> check the stable Provider idempotency key, and verify the deterministic Artifact. A paused Worker A may resume,
> so final PostgreSQL writes must be guarded by the current lease token, an unexpired lease, and equality with the current persisted fencing generation (minted durably at takeover), while the Provider side
> effect is protected by its own idempotency key. Redis coordinates work, but PostgreSQL remains the durable
> business authority."

Assessment: the student named the right foundation (reconcile durable facts + idempotency + Artifact); the strong
answer adds fail-closed admission, no mass-restart, the degradation-monitoring window, and the
ownership/fencing guard.

## Common Weak Answer

"Use a Redis lock and an `INCR`/`DECR` counter; if Redis fails over, just retry — the lease and lock keep
everything exactly-once."

## Strong Answer

"Rate limiting needs an atomic read-modify-write (a short Lua), not a lock, and admission is not durable success —
PostgreSQL Job + Outbox is the acceptance truth with a `(tenant_id, idempotency_key)` uniqueness boundary. A lease
permits takeover but can't stop a paused owner or an in-flight Provider call, so I use compare-and-delete release,
a monotonic fencing generation for stale-write rejection in PostgreSQL, and stable Provider idempotency +
Artifact reconciliation for external effects. Redis can lose counters on eviction/failover, so I isolate
coordination capacity, fail closed on new expensive admission during an outage, avoid mass-restarting Workers, and
monitor the degradation."

---

# Mental Model Summary

```text
1.  Redis COORDINATES and PROTECTS; PostgreSQL Job/Attempt/Event/Outbox is the durable business authority.
2.  A concurrent admission race is missing ATOMICITY, not necessarily a lock.
3.  Rate-limit decision = atomic read -> check -> INCR-if-allowed -> TTL -> allow/reject, in ONE Lua step.
4.  NOT GET->check->SET; NOT INCR-then-DECR compensate. Lua is the atomic boundary (don't nest MULTI/EXEC or wrap one command).
5.  Admission != durable Job success: a consumed token is an allowed attempt; don't compensate the counter.
6.  Algorithms: fixed (cheap, boundary burst) / first-write TTL (request-anchored) / sliding (smooth) / token bucket (burst+rate).
7.  API idempotency = client key + PG UNIQUE (tenant_id, idempotency_key); API vs Provider vs notification identities are SEPARATE.
8.  A Redis lock reduces optional duplicate work; the PG unique constraint is the final Job-identity authority.
9.  Lease expiry permits TAKEOVER; it does NOT stop a paused owner or an in-flight Provider call.
10. Safe release = atomic compare-and-delete (delete only if the stored token is mine); it can't stop external work.
11. Fencing = a MONOTONIC generation minted durably in a PostgreSQL claim/takeover tx (NOT a rollback-able Redis INCR); a UUID lease token cannot fence. Generic downstream rule: accept only last_accepted_fence < incoming_fence, then persist it.
12. Job Complete guard = running + current lease token + unexpired lease + fencing_generation = the current PERSISTED generation (EQUALITY, not >= / >).
13. RDB/AOF/replication/failover/eviction can lose counters = TEMPORARY protection degradation (monitor; isolate from cache).
14. Security = network + auth + ACL (command + ratelimit:* prefix) + TLS + deny FLUSHALL/CONFIG + audit/monitor.
15. Managed Redis runs infra, NOT business responsibility; Redis is memory-resident (persistence is a disk/recovery cost).
16. Outage: API fail-closed on new expensive admission; no Worker mass-restart; drain + reconcile durable facts.

Starting model -> reasoning -> correction -> final model:
Initial: a lock fixes the two-Pod race; INCR-then-DECR compensates a rejection; a lease/lock stops the old Worker;
Attempt/Event/Outbox deduplicate a POST; managed Redis "self-operates" config.
Reasoning: the student protected PostgreSQL from compensation coupling, chose sliding window / token bucket well,
reasoned that a lease can't stop external work, and described a monotonic fencing comparison in the database.
Correction: the race needs atomicity not a lock; keep check+increment+TTL in one atomic step; a lease permits
takeover but can't stop a paused owner; API identity is a client key + PG uniqueness (Worker facts may not exist);
fencing must be ordered AND durably allocated in PostgreSQL (not by a rollback-able Redis INCR), with the Job Complete guard using equality with the current persisted generation; managed infra does not transfer correctness responsibility.
Final: Redis only coordinates/protects; durable facts stay PostgreSQL Job/Attempt/Event/Outbox + reconciled
Provider/Artifact; lease expiry enables takeover but not a stop; fencing is an ordered generation a durable
downstream uses to reject stale writes; eviction/failover temporarily weaken protection; the API fail-closes new
expensive admission during a Redis outage and Workers are drained/reconciled, not mass-restarted.
```

---

# Today's Takeaway

Redis coordinates and protects; PostgreSQL remains the durable business authority. Make admission an atomic
read-modify-write (a short Lua), treat a consumed token as an allowed attempt rather than a created Job, decide
Job identity at a PostgreSQL uniqueness boundary, and remember that a lease permits takeover but never stops a
paused owner or an in-flight Provider call — so stale writes are rejected by a durably-allocated (PostgreSQL) monotonic fencing generation compared by equality and
the PostgreSQL completion guard, and external effects are protected by stable Provider idempotency and Artifact
reconciliation.

Most important mental model: Redis admission/lease is coordination, not truth. Most important production risk: a
non-atomic counter leaking duplicate expensive admissions, or a stale owner writing `succeeded` / calling the
Provider after takeover. Most important trade-off: fail-closed vs fail-open on a Redis outage (fail closed on new
expensive admission). Most important connection: the Day34/Day37 completion guard extended with a fencing
generation. Most important interview answer: the two-Pod race is missing atomicity — use a short Lua read →
check → increment → TTL.

Validation status: this lesson is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT
VALIDATED. No Redis, Lua, `MULTI/EXEC`, `WATCH`, ACL, TLS, persistence, eviction, failover, rate limiter, FastAPI
endpoint, PostgreSQL SQL, Provider, or Object Storage was executed; every number (60/min, 30s, capacity 10, refill
1/s) is a static design example. The Day42 capstone is a future boundary.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain the core mental model — Redis coordinates/protects, PostgreSQL is the durable authority — in plain English?
- [ ] Can I explain why the two-Pod race is missing atomicity, not a lock?
- [ ] Can I write the atomic admission (Lua read → check → INCR-if-allowed → TTL) and reject INCR-then-DECR?
- [ ] Can I explain why admission is not durable success and why I don't compensate the counter?
- [ ] Can I compare fixed / first-write TTL / sliding / token bucket and do the capacity-10 refill-1/s calculation?
- [ ] Can I design API idempotency with a client key + PostgreSQL (tenant_id, idempotency_key) uniqueness?
- [ ] Can I explain why a lease permits takeover but can't stop a paused owner or an in-flight Provider call?
- [ ] Can I write compare-and-delete safe release and say what it does not stop?
- [ ] Can I distinguish an opaque lease token from a monotonic fencing token, and state the completion guard?
- [ ] Can I treat RDB/AOF/replication/failover/eviction loss as monitored protection degradation and isolate coordination capacity?
- [ ] Can I design the ACL (command + ratelimit:* prefix) and explain why managed Redis doesn't transfer responsibility?
- [ ] Can I contain the integrated failover + lease + Provider incident (fail-closed admission, no mass restart, reconcile)?
```

Preparation for Day42 (Backend Data Design Capstone): review this lesson's coordination boundary and the
`redis/redis-coordination-and-production-safety-design.md` artifact, then be ready to integrate PostgreSQL
schema/constraints/transactions/concurrency/indexes/migrations/operations with the Redis cache/messaging/
coordination boundaries into one data-ownership, failure, recovery, and verification model — durable truth stays
in PostgreSQL. Keep SQLAlchemy/Alembic (Phase 4) out of scope.

---

Engineering Artifact: [projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md](../../projects/ai-backend-data-layer/redis/redis-coordination-and-production-safety-design.md)
