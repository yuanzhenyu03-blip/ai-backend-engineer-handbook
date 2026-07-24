# Lesson 39 — Redis Cache Design and Consistency

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day38 — Redis Foundations and Data Structures

Previous Lesson: [Day38 — Redis Foundations and Data Structures](day38-redis-foundations-and-data-structures.md)

Next Lesson: Day40 — Redis Messaging and Queue Semantics (planned — see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day40 lesson file does not exist yet)

Engineering Artifact: The Day39 Redis cache consistency design (`projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md`) — the per-endpoint cache-aside/invalidation contracts, commit-before-invalidate ordering, key versioning, TTL+jitter, stampede/single-flight/SWR, fail-open vs fail-closed table, negative caching, correctness metrics, Outbox invalidation recovery, and the v2 cache-contract incident, all labelled conceptual/static — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

Redis Cheat Sheet: [cheat_sheets/redis.md](../../cheat_sheets/redis.md)

Redis Interview: [interview/redis.md](../../interview/redis.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises: 100-130 minutes
Hands-on cache-contract + invalidation/SWR design: 100-130 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why a cache hit is not truth and a cache miss is not a Job failure, and judge every cache decision against the committed PostgreSQL state.
2. Implement the cache-aside read path (hit / miss / best-effort repopulate) so a cache write failure never invalidates a correct PostgreSQL response.
3. Order a state change as commit-first, invalidate-after, and explain the pre-commit re-cache race that reverse ordering creates.
4. Invalidate every affected cache view (Job detail and the tenant recent-completed list), not just one.
5. Decide when a representation change needs a new versioned key (`v2`) versus an additive optional field.
6. Apply TTL + jitter to prevent cache avalanche, and explain why single-flight fixes one hot key but not synchronized expiry of many keys.
7. Design hot-key protection with a single-flight leader, bounded followers, backoff+jitter, and stale-while-revalidate for tolerant reads only.
8. Classify endpoints fail-open vs fail-closed, and defend why `POST /cancel` must fail closed against a guarded PostgreSQL write.
9. Use short, tenant-scoped negative caching against penetration without turning it into a security decision.
10. Measure cache correctness (commit→invalidation delay, cache age, stale-terminal rate, Redis-vs-PostgreSQL agreement), not just hit ratio.
11. Recover an unknown cache-delete outcome with a transactional Outbox intent and a retryable idempotent `DEL`, never by redoing a Job transition or a Provider call.
12. Choose the correct rollback target in a v2 cache incident — the cache contract, never committed PostgreSQL truth or Provider work.

---

# Why This Matters

Day38 drew the ownership line: PostgreSQL owns durable Job truth, Redis is rebuildable acceleration. Day39
is where that line gets tested by real traffic. The opening scene is exact and uncomfortable: PostgreSQL has
committed a Job from `running` to `succeeded`, but Redis still serves a `running` detail view. Nothing is
broken — this is the normal behaviour of a cache — and the engineering job is to make that gap **bounded,
observable, and safe**, not to pretend it does not exist.

The production stakes are concrete. Get the invalidation order wrong and a reader re-caches stale state with
a fresh TTL. Give every key the same TTL and a synchronized expiry stampedes PostgreSQL into a connection-
pool collapse. Let a stale cache value authorize a `POST /cancel` and you corrupt state or cancel a Job that
already succeeded. Trust a 99% hit ratio and you ship a system that is fast and confidently wrong. Retry an
uncertain cache delete by "resubmitting" and you risk re-running an expensive, side-effectful Provider call.

Cache consistency is therefore not "add a TTL." It is a per-endpoint contract spanning the PostgreSQL commit,
post-commit invalidation, retryable invalidation intent, bounded miss handling, serialization/version
compatibility, and correctness observability. This lesson builds that contract.

Everything here is design and reasoning. Nothing was executed — no Redis, `redis-cli`, cache API, PostgreSQL
integration, Outbox Relay, benchmark, stampede, eviction, or hot key — and the artifact is labelled that way.

---

# Roadmap Position

```text
Day37 operate PostgreSQL reliably     Day38 Redis as bounded, rebuildable acceleration
Day39 cache consistency around the durable truth   <-- you are here
Day40 messaging / queue semantics (Lists / Pub-Sub / Streams)
Day41 atomic composition (MULTI/EXEC, Lua), coordination, full rate limiting
Day42 the integrated data ownership + failure + recovery model
```

Knowledge continuity:

```text
Previous knowledge
  Day33/34 guarded transitions + Lease ownership (the authority for a sensitive write)
  Day37 connection budgets, timeouts, readiness (how a fallback protects PostgreSQL)
  Day38 Redis ownership: rebuildable, tenant-scoped, versioned keys; a missing key is a cache-miss
        |
        v
Current lesson
  cache-aside reads + commit-then-invalidate + TTL/jitter + single-flight/SWR + fail-open/closed +
  negative caching + correctness metrics + Outbox invalidation recovery
        |
        v
Future production usage
  Day40 messaging reuses "Redis transport does not own durable truth"
  Day41 reuses single-flight / backoff / atomic-boundary reasoning for rate limits + coordination
  Day42 combines cache consistency, messaging, PostgreSQL truth, Object Storage bytes, recovery/verification
```

Mental models reused by name: the Day33/34 guarded state transition (authority for `POST /cancel`), the
Day37 bounded-fallback budget (protecting PostgreSQL under miss storms), the Day38 versioned tenant-scoped
key contract (extended here to a cache-representation `v2`), and the Phase 3 Transactional Outbox (now
carrying a cache-invalidation intent).

---

# Lesson Map

```text
1. Cache hit != truth, miss != failure   -> judge against the committed PostgreSQL state
2. Cache-aside read                        -> hit-if-tolerable / miss -> PostgreSQL + best-effort repopulate
3. Commit THEN invalidate                  -> reverse order re-caches stale state (pre-commit race)
4. Invalidate every affected view          -> Job detail AND recent-completed list
5. Representation versioning               -> incompatible change = new v-key; additive optional = same version
6. TTL + jitter                            -> avalanche control; single-flight != synchronized-expiry fix
7. Stampede / single-flight / SWR          -> one leader, bounded followers, stale-for-tolerant-reads
8. Fail-open vs fail-closed                -> GET progress open; POST cancel closed on a guarded write
9. Negative caching / penetration          -> short tenant-scoped; not a security control
10. Hot key + correctness metrics          -> a hit can overload; freshness signals, not hit ratio alone
11. Invalidation recovery (Outbox + DEL)   -> retryable idempotent delete; never redo transition/Provider
12. v2 cache-contract incident             -> reconcile first; roll back the CACHE contract only on evidence
```

---

# Core Mental Model

```text
PostgreSQL COMMIT = the moment of authority.  Redis cache = a rebuildable PROJECTION that may be STALE/ABSENT.

READ      cache-aside: GET cache -> hit if the endpoint tolerates it; else read PostgreSQL, return, then
          best-effort SET with TTL. A cache write failure never invalidates a correct PostgreSQL answer.
WRITE     COMMIT PostgreSQL first -> THEN invalidate EVERY affected view. Deleting before commit re-caches
          the old state; a small stale window remains even after (a cache is a view, not truth).
EXPIRE    TTL bounds staleness; JITTER prevents synchronized avalanche; SINGLE-FLIGHT protects ONE hot key.
SERVE     tolerant reads may use STALE-WHILE-REVALIDATE; sensitive writes FAIL CLOSED on a guarded
          PostgreSQL write -- a cache never authorizes.
OBSERVE   measure FRESHNESS/CORRECTNESS (commit->invalidation delay, cache age, stale-terminal, agreement),
          not hit ratio alone.
RECOVER   record the invalidation INTENT in the Outbox; a Relay retries an idempotent DEL; never redo the
          Job transition or the Provider call.
```

---

# Main Concepts

## Concept 1: A stale cache does not override committed truth

### Tech Lead Question

PostgreSQL has committed a Job from `running` to `succeeded`, but Redis still serves a `running` detail
cache. Which state wins, and does a short TTL fix it?

### Student Thinking

The student anchored on PostgreSQL as the authoritative store and reasoned about what a TTL actually buys —
faster cleanup, not synchronization.

### Student Answer

> "API应该以postgresql持久化状态为准。TTL设置短，只能加快cache清理的过程，清理后也不是马上去数据库同步状态。"

### Tech Lead Review

Correct, including the subtle part. PostgreSQL's committed state is authoritative; the cache is a projection
that is allowed to lag. A short TTL only **bounds** the stale lifetime — it is not immediate synchronization,
and it does not push the new state into Redis. Worse, a very short TTL across many keys increases PostgreSQL
pressure. Durable state changes require explicit **post-commit invalidation**, not a hope that the TTL is
short enough.

### Engineering Thinking

The cache exists to reduce load and latency, not to hold truth. Treat every cached value as "possibly stale"
and design the endpoint's tolerance for that staleness deliberately.

## Concept 2: The cache-aside read path

### Tech Lead Question

A read comes in. Walk the cache-aside path, and say what happens on a miss.

### Student Thinking

The student had the standard cache-aside shape: try cache, on miss go to the database and populate.

### Student Answer

> "从PostgreSQL数据库中加载数据并在redis填充缓存。"

### Tech Lead Review

Right. The full contract: `GET` the key; on a **hit**, return the cached view **only when the endpoint
tolerates that staleness**; on a **miss**, read authoritative data from PostgreSQL, return it, then
**best-effort** repopulate Redis with a TTL. The one rule to add: a cache **write** failure must not
invalidate an already-correct PostgreSQL response — you already have the truth in hand, so a failed `SET`
just means "no cache this time," never a failed request.

### Engineering Thinking

Cache-aside keeps the database authoritative and the cache optional. Because the authoritative read happens
before the repopulate, Redis being slow or down degrades latency, not correctness.

## Concept 3: Commit first, then invalidate

### Tech Lead Question

On `running -> succeeded`, do you delete the cache before or after the PostgreSQL commit?

### Student Thinking

The student chose post-commit deletion.

### Student Answer

> "提交后删除"

### Tech Lead Review

Correct — and the reason matters more than the choice. If you **delete before commit**, a race opens: another
request misses the cache, reads the **old `running`** row from PostgreSQL (the new state has not committed
yet), and **re-caches that stale state** with a fresh TTL. Now the cache is confidently wrong. Committing
first and invalidating after closes that race. A small stale window still exists between the commit and the
invalidation completing — that is expected, because Redis is an acceleration view, not truth. The baseline is
**invalidate-after-commit**, not writing a guessed "succeeded" view straight into Redis (a write-through of a
guessed final view has concurrency/retry/ordering risk).

### Engineering Thinking

Ordering is the cheap correctness lever. Commit-then-invalidate turns "the cache might be stale" into "the
cache is briefly stale and then correct," instead of "the cache is stale with a fresh TTL."

## Concept 4: Invalidate every affected view

### Tech Lead Question

The Job's status changed. The Job-detail cache is obvious — is that all you invalidate?

### Student Thinking

The student saw two affected views and ordered them, reasoning that the second view is the recent-completed
list.

### Student Answer

> "先更新A再，更新B，因为B的意思是最近完成的job。"

### Tech Lead Review

The insight — there are two affected views — is exactly right. On `running -> succeeded` you must invalidate
**both** the Job-detail cache **and** the tenant recent-completed-Jobs view; invalidating only the detail
leaves the list inconsistent (the Job is done but missing from "recent completed"). One correction to the
framing: the baseline is to **invalidate every affected view after commit**, not to directly "update A then
update B" with guessed values — a direct cache update carries concurrency, retry, and ordering risk. Delete
the affected keys and let the next cache-aside read rebuild them from PostgreSQL.

### Engineering Thinking

A state change fans out to every projection that derives from it. Enumerate the affected views per transition
so none is silently left stale.

## Concept 5: Cache representation and versioning

### Tech Lead Question

You change `progress` from `42` (an integer 0-100) to `0.42` (a float 0-1). Can the cache keep the same key?

### Student Thinking

The student flagged the compatibility problem immediately.

### Student Answer

> "因为会造成兼容性问题。"

### Tech Lead Review

Correct — the cache JSON is a **consumer contract**, and reinterpreting `progress` is an **incompatible**
change (same field, different meaning). While old and new APIs coexist you need a **new versioned key**
(`v2`), e.g. `...:job-detail:v1:{job}` (0-100) alongside `...:job-detail:v2:{job}` (0-1), so a v1 client never
parses a v2 value as `42%`. The precision to add: a **compatible** change — an additive **optional** field —
does **not** automatically require a new key version.

### Engineering Thinking

Version the cache only on an incompatible break, exactly like the Day38 key-version rule. A version is a
migration boundary, not a per-field reflex.

## Concept 6: TTL, jitter, and synchronized expiry

### Tech Lead Question

Many keys share one fixed TTL and all expire at the same instant. What happens, and how do you fix it?

### Student Thinking

The student predicted the avalanche and reached for a leader/wait pattern.

### Student Answer

> "会发生所有的cache会一起丢掉...需要用其中一个作为leader来请求，其他进行等待。"

### Tech Lead Review

The avalanche prediction is correct: a fixed synchronized TTL makes many **distinct** keys expire together
and all fall back to PostgreSQL at once. The correction is which tool solves which problem. **TTL jitter**
(base ± a random spread) distributes expiry over time and is the right fix for **synchronized expiry of many
keys**. **Single-flight** (electing one leader) protects **one hot key** after a miss — it cannot solve one
million *distinct* keys expiring together, because there is no single key to elect a leader for. Use jitter
for the avalanche; keep single-flight for the hot key.

### Engineering Thinking

Match the mechanism to the failure shape: many-keys-at-once is a distribution problem (jitter); one-key-under-
load is a coordination problem (single-flight).

## Concept 7: Stampede, single-flight, and stale-while-revalidate

### Tech Lead Question

Fifty thousand requests miss the same hot key at once. How do you serve them without stampeding PostgreSQL,
and what may a progress page return meanwhile?

### Student Thinking

The student connected the stampede to a pool-exhaustion risk and to a leader rebuild, and separately accepted
returning a stale progress view.

### Student Answer

> "会造成缓存雪崩PostgreSQL请求压力增大，连接池被耗尽，应该让其中一个请求负责回源和重建 cache。"

> "先立刻返回旧的running。"

### Tech Lead Review

Both correct. Elect **one leader** to read PostgreSQL / rebuild the value; **followers wait only within a
bounded deadline** or receive an **allowed stale value**. The rule to add: on leader timeout, do **not** fan
out all followers to PostgreSQL — use bounded retry, exponential **backoff + jitter**, circuit/backoff
behaviour, and endpoint-specific degradation. Returning the old `running` view immediately is exactly
**stale-while-revalidate**: serve a short stale value while **one** background refresh obtains PostgreSQL
truth. SWR is fine for a tolerant progress view; it is **not** allowed for state-changing/sensitive
operations.

### Engineering Thinking

A stampede is solved by *coordination + degradation*, not by adding database capacity. SWR trades a little
freshness for a lot of stability on reads that can tolerate it.

## Concept 8: Fail-open vs fail-closed

### Tech Lead Question

Classify `GET /jobs/{job_id}/progress` and `POST /jobs/{job_id}/cancel`: which may fail open, which must fail
closed?

### Student Thinking

The student classified the two endpoints and, on cancel, reasoned from the domain: some Jobs have already
succeeded and cannot be cancelled.

### Student Answer

> "A. B" (A = progress read, B = cancel write)

> "不能，POST /jobs/{job_id}/cancel有的job已经success，是无法进行cancel。"

### Tech Lead Review

Correct classification. `GET /progress` is tolerant — **fail-open** / controlled degradation (bounded SWR, a
short stale `running`) is acceptable. `POST /cancel` is sensitive — **fail-closed**: it must use PostgreSQL
authorization **plus** a guarded state transition (the Day33/Day34 pattern). The student's domain point is
the key insight: a Job that already committed `succeeded` cannot be cancelled — so a **cache** value can
never authorize the cancel, and even a PostgreSQL **pre-read** is not a substitute for the **guarded write**
that atomically checks the current state at write time.

### Engineering Thinking

Sensitivity sets the failure mode. Reads degrade; sensitive writes stop and defer to the authoritative
guarded write, because a wrong cancel is unrecoverable in a way a stale number is not.

## Concept 9: Negative caching and cache penetration

### Tech Lead Question

Requests keep asking for random non-existent Job IDs, missing the cache every time. What is happening, and
how do you protect PostgreSQL?

### Student Thinking

The student read it as an attack pattern and proposed briefly caching the "not found" result.

### Student Answer

> "这个问题应该是负载攻击。可以把Job 不存在的结果短暂缓存。"

### Tech Lead Review

The right instinct, sharpened. This is **cache penetration** — non-existent keys miss cache on every request
and hit PostgreSQL (it may be an attack or just a broken client). A **short, tenant-scoped negative cache**
("this id does not exist") absorbs the repeated misses. The constraints: keep it **short-lived**; a
**successful Job creation must invalidate** the negative entry (so a real new Job becomes visible); and it is
**never** a security/authorization decision — it only protects PostgreSQL from load.

### Engineering Thinking

Negative caching is a load shield, not an access-control mechanism. It buys the database breathing room while
staying short enough not to hide a legitimately created Job.

## Concept 10: Hot keys and correctness metrics

### Tech Lead Question

Your cache hit ratio is 99% but users report a `succeeded` Job still showing `running`. What does the hit
ratio actually prove, and what else must you measure? And can a cache **hit** ever overload you?

### Student Thinking

On the hot-key overload question the student was initially unsure; on the stale-response question the student
reached for the miss ratio as the signal.

### Student Answer

> (hot key) "不知道"

> (high hit ratio but stale) "miss ratio"

### Tech Lead Review

"I don't know" is an honest start for the hot-key case, and the answer is: **yes, a cache hit can still
overload Redis** — 50,000 requests to **one** key / node / network path is a hot key, and a high hit ratio
hides it. On the stale response, the miss ratio is not the right signal either: hit **and** miss ratio
measure cache **efficiency**, not **truth**. To catch a stale `succeeded`, measure **correctness**:
PostgreSQL commit → invalidation **delay/failure/backlog**, **cache age**, **stale terminal** responses,
sampled **Redis-vs-PostgreSQL agreement**, plus Redis latency/CPU/network, per-key/per-tenant hotness,
memory/eviction, and PostgreSQL pool waits under fallback.

### Engineering Thinking

A high hit ratio can mean "fast and confidently wrong." Freshness and agreement are the metrics that catch
correctness failures; efficiency metrics never will.

## Concept 11: Invalidation recovery with the Outbox

### Tech Lead Question

PostgreSQL committed `succeeded`, but the cache `DEL` network call timed out — you don't know if the delete
happened. What is the **most dangerous** thing to do, and what is the safe recovery?

### Student Thinking

The student identified the dangerous action (blindly re-submitting) and, separately on the Provider question,
reasoned that re-calling a Provider needs an idempotency key.

### Student Answer

> "最危险的操作动作是直接重新提交。手动删除。"

> (Provider) "因为重新调用provider需要结合幂等key,防止二次调用。"

### Tech Lead Review

The dangerous-action call is correct: **never redo the Job transition** (and never re-call the Provider)
because a cache delete is uncertain. "Manual delete" works once but does not scale or survive a crash; the
durable pattern is to record the cache-invalidation **intent transactionally with the state change**
(Transactional Outbox), and have a **Relay retry an idempotent `DEL`** (deleting an already-absent key is
harmless). TTL bounds the residual stale window as a backstop. And the student's Provider point is the right
contrast: cache-delete idempotency is **unlike** Provider retries, which need a **stable idempotency key** and
durable evidence/Artifact reconciliation to avoid a costly double call.

### Engineering Thinking

Make invalidation a durable, retryable intent rather than a fragile inline delete. An idempotent `DEL` can be
retried freely; a Provider call cannot, which is why they get different recovery machinery.

## Concept 12: The v2 cache-contract incident

### Tech Lead Question

The v2 Job cache is deployed, PostgreSQL committed `succeeded`, the invalidation Relay times out, and 50,000
users still read v1 `running`. Do you roll back to v1?

### Student Thinking

The student's first move was to roll back to v1, then — reasoning about where the actual authority and the
actual fault lie — corrected to rolling back the v2 cache contract only.

### Student Answer

> (initial) "先回滚到V1版本。"

> (corrected) "Redis v2 cache contract，因为v2不兼容错误解释数据，PostgreSQL 的 Job state是权威持久化状态，provieder避免二次调用。"

### Tech Lead Review

Rolling back to v1 first is the trap: **v1 is stale too** (it also holds `running`), and there is **no
evidence** the v2 *contract* is faulty — the symptom is a timed-out invalidation, not a bad representation.
The correct first action is to **retry/reconcile the invalidation**, serve bounded SWR/single-flight for the
normal UI, and protect PostgreSQL. Only **if** evidence proves v2 misinterprets the data (e.g. it renders
`0.42` as `42%`) do you roll back the **Redis v2 cache contract/traffic**, invalidate v2 keys, and rebuild
from PostgreSQL. The student's corrected answer names all three anchors: v2 is the incompatible/faulty
contract, PostgreSQL Job state is authoritative and is **not** a rollback target, and the Provider must not
be called twice.

### Engineering Thinking

Separate the symptom (stale cache) from the fault (a bad contract). The rollback target is always the cache
layer that is actually wrong — never the committed durable truth and never the external Provider effect.

---

# Common Misconceptions

Cache freshness

❌ "A short TTL keeps the cache in sync with PostgreSQL."
✅ A TTL only bounds how long a value may be stale; it never pushes the new committed state into Redis, and a
very short TTL raises PostgreSQL load. Durable changes need post-commit invalidation.

Why beginners think this: "expires soon" feels like "updates soon."
How to remember: TTL bounds staleness; invalidation removes it.

Invalidation ordering

❌ "Delete the cache first so nobody reads the old value."
✅ Pre-commit delete lets a reader load the old `running` row and re-cache it with a fresh TTL before the
commit. Commit first, then invalidate.

Why beginners think this: deleting early sounds safer.
How to remember: commit is authority; invalidate only what is already true.

Partial invalidation

❌ "Invalidate the Job-detail cache and you're done."
✅ Every affected view must be invalidated — detail **and** the recent-completed list — or projections
disagree.

Why beginners think this: the detail view is the one you were looking at.
How to remember: one transition fans out to every derived view.

Expiry storms

❌ "Single-flight fixes cache avalanche."
✅ Single-flight protects one hot key; a million distinct keys expiring together is solved by TTL jitter.

Why beginners think this: both involve misses and rebuilding.
How to remember: jitter for many keys, single-flight for one key.

Sensitive writes

❌ "If the cache says `running`, we can cancel."
✅ A cache never authorizes a state-changing write. `POST /cancel` fails closed on a guarded PostgreSQL write;
even a PostgreSQL pre-read is not a substitute.

Why beginners think this: the cache "just told us" the state.
How to remember: reads may degrade; sensitive writes defer to the guarded write.

Cache health

❌ "99% hit ratio means the cache is healthy."
✅ Hit ratio measures efficiency, not truth; a hit can overload a hot key, and a stale `succeeded` still reads
`running`. Measure freshness/correctness.

Why beginners think this: high hit ratio looks like success.
How to remember: fast is not the same as fresh.

Invalidation recovery

❌ "The cache delete timed out, so resubmit the Job / re-call the Provider."
✅ Never redo the transition or the Provider call. Record the invalidation intent in the Outbox and retry an
idempotent `DEL`.

Why beginners think this: "unknown result" feels like "do it again."
How to remember: an idempotent `DEL` is retryable; a Provider call is not.

Incident rollback

❌ "Stale v2 cache? Roll back to v1."
✅ v1 is stale too, and there is no evidence the v2 contract is faulty. Reconcile first; roll back the cache
contract only on proven incompatibility, never PostgreSQL truth or Provider work.

Why beginners think this: rolling back the newest change feels safe.
How to remember: roll back the layer that is actually wrong — the cache, not the truth.

---

# Engineering Trade-offs

## Invalidate-after-commit vs write-through the final view

Invalidate-after-commit is simple and safe: delete the affected keys and let the next read rebuild from
PostgreSQL. Write-through (pushing the guessed final value straight into Redis) can save one rebuild but adds
concurrency, retry, and ordering risk and can write a wrong value. Choose invalidation as the baseline; reach
for write-through only for a hot read where the rebuild cost is proven and the value is unambiguous.

## Short TTL vs long TTL vs jitter

A short TTL bounds staleness tightly but raises miss rate and PostgreSQL load; a long TTL is cheap but serves
older data. Neither addresses synchronized expiry — that is what jitter is for. Pick a TTL from the endpoint's
staleness tolerance, then always add jitter so expiry is spread rather than synchronized.

## Fail-open vs fail-closed

Fail-open maximizes availability and is right for tolerant reads (a slightly stale progress number). Fail-
closed maximizes correctness and is mandatory for sensitive writes (cancel, state transitions). The trade-off
is availability vs correctness, and it is decided per endpoint by the cost of being wrong, not globally.

## Single-flight/SWR vs letting all requests through

Single-flight and SWR protect the database and keep latency stable under a hot key, at the cost of some
followers seeing a slightly stale value or waiting briefly. Letting every request through is simpler but
stampedes PostgreSQL. For hot, tolerant reads, coordination wins; for cold or unique keys it is unnecessary
overhead.

## Negative caching vs always hitting PostgreSQL

A short tenant-scoped negative cache shields PostgreSQL from penetration by non-existent IDs, at the cost of a
brief window where a just-created Job could read as "not found" — which is why creation must invalidate it and
the TTL must be short. Without it, a broken client or attacker can drive unbounded misses into the database.

## Outbox invalidation intent vs inline best-effort delete

An inline `DEL` is one fewer moving part but is lost on a crash or timeout, leaving an unbounded stale window.
An Outbox intent + retryable idempotent `DEL` is durable and self-healing at the cost of the Outbox/Relay
machinery you already run for Phase 3. For terminal transitions where a stale `succeeded` matters, the durable
path is worth it; TTL remains the backstop either way.

---

# Hands-on Exercises

Design/paper only. Nothing here was executed against a live Redis or PostgreSQL; treat every snippet as a
design artifact.

### Exercise 1: Trace the stale-vs-committed read

Question: PostgreSQL committed `succeeded`; Redis serves `running`. A `GET /progress` arrives.

Think First: which state is authoritative, and what may the endpoint return?

Starter Artifact:

```text
cache GET ai:tenant:{t}:job-detail:v1:{job}  -> HIT {status: running}
```

Expected Output: the endpoint may return the short stale `running` (tolerant read), while a background refresh
rebuilds from PostgreSQL; the authoritative state is the committed `succeeded`.

Explanation: a TTL only bounds the stale window; correctness comes from post-commit invalidation + SWR, not
from the cache being "recent."

Follow-up Question: what changes if this is `POST /cancel` instead of `GET /progress`?

### Exercise 2: Break and fix the invalidation order

Question: show the pre-commit-delete race on a timeline, then fix the ordering.

Think First: what does a concurrent reader see between the delete and the commit?

Expected Output:

```text
BROKEN: DEL cache -> reader miss -> read OLD running from PG -> SET cache running (fresh TTL) -> COMMIT succeeded
FIXED:  COMMIT succeeded -> invalidate detail + recent-completed -> next read rebuilds succeeded
```

Explanation: reverse ordering re-caches stale state with a fresh TTL; commit-first closes the race.

Follow-up Question: which keys must the fixed path invalidate, and why is one not enough?

### Exercise 3: Cache-aside miss with best-effort repopulate

Question: write the miss path and state what happens if the `SET` fails.

Expected Output:

```text
GET key -> MISS -> read PG (authoritative) -> return it -> best-effort SET key TTL(base±jitter)
SET fails -> response is still correct; just no cache this time
```

Explanation: the authoritative read precedes the repopulate, so a cache write failure never fails the request.

Follow-up Question: where does jitter go, and what failure does it prevent?

### Exercise 4: Hot-key stampede with a bounded leader

Question: 50,000 requests miss one key. Design the serve path and the leader-timeout behaviour.

Think First: what do followers do while the leader rebuilds, and what must they not do on timeout?

Expected Output: elect one single-flight leader to read PostgreSQL; followers wait within a bounded deadline or
get an allowed stale value; on leader timeout use bounded retry + backoff + jitter, not a full fan-out.

Explanation: coordination + degradation protects PostgreSQL; adding DB capacity does not.

Follow-up Question: which endpoints may serve the stale value, and which may not?

### Exercise 5: Fail-open vs fail-closed table (design judgment)

Question: classify `GET /progress` and `POST /cancel`, and justify the cancel path.

Expected Output:

```text
GET /jobs/{id}/progress  -> fail-open / bounded SWR
POST /jobs/{id}/cancel   -> fail-closed: PG authorization + guarded state transition; cache cannot authorize
```

Explanation: a Job already `succeeded` cannot be cancelled; the guarded write is the only authority.

Follow-up Question: why is a PostgreSQL pre-read still not a substitute for the guarded write?

### Exercise 6: v2 cache-contract incident (reusable artifact)

Question: v2 deployed, PostgreSQL `succeeded`, invalidation Relay timed out, 50,000 users read v1 `running`.
Give the first action and the only condition for rolling back the cache contract.

Expected Output: reconcile/retry invalidation + bounded SWR + protect PostgreSQL first; roll back the v2 cache
contract only on proof of incompatibility (e.g. `0.42` shown as `42%`); never roll back committed PostgreSQL
truth or rerun Provider work. This exercise maps to the artifact's incident section.

Explanation: separate symptom (stale cache) from fault (bad contract); roll back only the layer that is wrong.

Follow-up Question: why is automatic rollback to v1 wrong here?

---

# Relevant Framework Connections

## PostgreSQL

PostgreSQL is the authority every cache decision defers to: the **commit** is the moment of truth, commit
ordering makes invalidation safe, the **guarded state transition** (Day33/34) authorizes `POST /cancel`, the
**Outbox** carries the invalidation intent, and Day37 **bounded pools/timeouts** keep a miss storm or fallback
from exhausting connections. Watch for pre-commit invalidation and for unbounded fallback under a stampede.

## Redis

Redis holds the cache-aside views, TTL/jitter, invalidation targets, single-flight/SWR coordination, negative
cache, and hot-key/eviction/memory signals. Watch that no cached value is ever treated as authoritative, that
every key is tenant-scoped and versioned, and that hot keys are observed even at a high hit ratio.

## FastAPI / API layer

The API layer is where endpoint sensitivity becomes a failure mode: `GET /progress` degrades (fail-open,
bounded SWR) while `POST /cancel` fails closed on the guarded write. Watch that a handler never lets a cache
value authorize a sensitive write, and that a cache write failure never turns a correct response into an
error.

## Worker / Relay / Outbox

The Worker commits the durable transition and enqueues the invalidation intent; the Relay retries an
idempotent `DEL`. Watch that the transition and the intent are recorded in the **same** transaction, and that
an uncertain delete never triggers a redo of the transition or a Provider call.

---

# AI Backend Connections

## Long-running Job progress and completion UI

The progress/completion views users poll during an eight-minute model call are exactly the tolerant reads that
benefit from cache-aside + SWR: return a short stale `running` while refreshing from PostgreSQL, and invalidate
both the detail and the recent-completed list on `succeeded`. A stale terminal state (`succeeded` shown as
`running`) is the correctness bug to measure, not the hit ratio.

## Expensive external Provider calls

Because Provider calls are costly and side-effectful, an **uncertain cache delete must never** trigger a redo:
the Outbox + idempotent `DEL` recovery exists precisely so cache uncertainty never re-runs a model call.
Provider retries need a stable idempotency key and Artifact reconciliation — a different mechanism from cache
invalidation.

## Tenant-scoped views

Job detail and recent-completed views are per tenant, so every cache key and every negative-cache entry is
tenant-scoped — the Day38 tenant-namespace rule carried into cache consistency, preventing one tenant's cached
view (or "not found") from leaking to another.

## Object Storage stays the byte owner

Large Artifact/PDF bytes remain in Object Storage; the cache carries small API **views**, never large
payloads. Caching a rendered view is fine; caching the bytes is a Day38 anti-pattern (memory, replication, and
eviction cost).

---

# English Interview

## Key Vocabulary

cache-aside, cache hit / miss, invalidation, post-commit invalidation, stale-while-revalidate (SWR),
single-flight, cache stampede, cache avalanche, TTL, jitter, negative caching, cache penetration, hot key,
fail-open / fail-closed, cache age, stale-terminal response, Transactional Outbox, idempotent `DEL`.

## Useful Expressions

"A cache hit is not proof of truth." · "Commit first, then invalidate every affected view." · "A missing key
is a cache miss, not a Job failure." · "Reads may fail open; sensitive writes fail closed on a guarded write."
· "Measure freshness, not just hit ratio."

## Beginner Question — Explain the cache-aside pattern.

Student answer (verbatim):

> "cache-aside means redis cache key LLT or eviction,request new cache from database,when a redis cache key is
> missing,API would request the authenticity durable truth in postgresql database and write into redis."

Strong answer:

> "Cache-aside is a pattern where the API reads Redis first. On a cache hit, it returns the cached response if
> that endpoint can tolerate it. On a cache miss, it reads the authoritative data from PostgreSQL, returns the
> result, and repopulates Redis with a TTL. A missing cache key is a cache miss, not a missing Job or a Job
> failure."

Assessment: the student had the miss→PostgreSQL→repopulate shape; the strong answer adds the hit-if-tolerable
condition and the miss-is-not-a-failure framing.

## Intermediate Question — Why invalidate the cache only after the PostgreSQL commit?

Student answer (verbatim):

> "beacause when the commit finshed, the durable truth write into database.invalidate a cache, next request
> would get the durable truth from database."

Strong answer:

> "The Worker should invalidate the cache only after the PostgreSQL transaction commits, because the committed
> row is the authoritative state. If it deletes the cache before the commit, another request can miss the
> cache, read the old running state from PostgreSQL, and write that stale value back into Redis. After the
> commit, invalidation ensures that the next cache-aside read rebuilds the cache from the new succeeded state."

Assessment: correct reasoning; the strong answer names the concrete pre-commit re-cache race.

## Senior Question — Design safe serving for a hot Job-progress key under a stampede.

Student answer (verbatim):

> "allow the stale cache response client.choose a work leader single- flight request durable truth from
> database,then write into redis ,other work wait for leader."

Strong answer:

> "For a normal Job-progress page, I would use stale-while-revalidate. I would return the 10-second-old cached
> running response if that staleness is acceptable, while electing one single-flight leader to read PostgreSQL
> and refresh Redis. Other requests would wait only within a bounded deadline or receive the stale response;
> they must not all fall back to PostgreSQL. I would use TTL jitter to avoid synchronized expiry, monitor cache
> age and invalidation failures as correctness signals, and use PostgreSQL guarded writes for sensitive
> operations such as cancellation rather than any stale cache value."

Assessment: the student had SWR + single-flight leader + followers-wait; the strong answer adds the bounded
deadline, no-full-fallback rule, jitter, correctness monitoring, and the fail-closed cancel boundary.

## Common Weak Answer

"Add a short TTL and a high hit ratio and the cache is consistent."

## Strong Answer

"TTL only bounds staleness and hit ratio only measures efficiency. Consistency is a per-endpoint contract:
cache-aside reads, commit-then-invalidate every affected view, TTL + jitter, single-flight/SWR for hot
tolerant reads, fail-closed guarded writes for sensitive operations, Outbox + idempotent DEL for invalidation
recovery, and freshness metrics (commit→invalidation delay, cache age, stale-terminal rate, Redis-vs-PostgreSQL
agreement)."

---

# Mental Model Summary

```text
1.  PostgreSQL COMMIT = authority; Redis cache = a rebuildable projection that may be stale or absent.
2.  A cache hit is not truth; a cache miss is not a Job failure.
3.  Cache-aside: hit if tolerable; miss -> PostgreSQL + best-effort repopulate; a failed SET never fails a
    correct response.
4.  Commit FIRST, then invalidate EVERY affected view; pre-commit delete re-caches stale state.
5.  A short TTL bounds staleness; it is not synchronization.
6.  Incompatible representation = new versioned key (v2); additive optional field = same version.
7.  TTL + jitter prevents avalanche; single-flight protects ONE hot key, not synchronized expiry.
8.  Hot reads: one single-flight leader + bounded followers + backoff/jitter; SWR for tolerant reads only.
9.  GET may fail open; sensitive POST fails closed on a guarded PostgreSQL write -- a cache never authorizes.
10. Short tenant-scoped negative caching stops penetration; it is load protection, not a security control.
11. A high hit ratio is not health; measure freshness/correctness and hot-key/eviction signals.
12. Invalidation recovery = Outbox intent + retryable idempotent DEL; never redo a transition or Provider call.
13. Roll back the CACHE contract only on proven incompatibility; never committed PostgreSQL truth or Provider.

Starting model -> reasoning -> correction -> final model:
Initial: a Redis miss returns to PostgreSQL and writes cache; staleness and expiry are risks to watch.
Reasoning: the student protected PostgreSQL from miss storms, accepted stale progress for UI, rejected
cache-based cancel decisions, and separated cache-contract rollback from durable truth.
Correction: cache consistency is NOT TTL alone -- it is an endpoint-specific contract across commit,
post-commit invalidation, retryable invalidation intent, bounded miss handling, serialization/version
compatibility, and correctness observability.
Final: PostgreSQL commit is authority and the cache may be stale or absent; cache-aside reads + post-commit
invalidation make it useful, TTL + jitter limit expiry load, single-flight/SWR protect hot reads, sensitive
writes fail closed against PostgreSQL, and cache metrics must measure freshness/correctness as well as hit
rate.
```

---

# Today's Takeaway

Cache consistency is a per-endpoint contract, not a TTL. The cache is a rebuildable projection of a PostgreSQL
truth that may be stale or absent, and every decision is judged against the committed state — commit first,
invalidate every affected view, expire with jitter, coordinate hot reads with single-flight/SWR, fail closed
on sensitive writes, recover invalidation through the Outbox, and measure freshness rather than hit rate.

Most important mental model: PostgreSQL commit is authority; the cache is a projection that may be stale.
Most important production risk: a stale terminal state or a pre-commit re-cache serving a `succeeded` Job as
`running`, or a synchronized-TTL avalanche exhausting the pool. Most important trade-off: fail-open reads vs
fail-closed sensitive writes. Most important connection: the guarded PostgreSQL write authorizes `POST /cancel`
— a cache never does. Most important interview answer: commit first, then invalidate, because the committed row
is the authoritative state.

Validation status: this lesson is CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT
VALIDATED. No Redis, `redis-cli`, cache API, PostgreSQL integration, Outbox Relay, benchmark, stampede,
eviction, hot key, TTL, or jitter was executed; numbers (10s, 50,000, TTL/jitter ranges) are illustrative.
Messaging (Day40), atomic composition/rate limiting (Day41), and the integrated model (Day42) are future
boundaries.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain the core mental model — PostgreSQL commit is authority, the cache is a projection that may be stale — in plain English?
- [ ] Can I explain why cache consistency is a per-endpoint contract, not just a TTL?
- [ ] Can I identify the pre-commit re-cache race and fix it with commit-then-invalidate?
- [ ] Can I name the main trade-off — fail-open reads vs fail-closed sensitive writes — and defend it?
- [ ] Can I connect cache consistency to PostgreSQL commits, the guarded cancel write, the Outbox, and an AI Job progress UI?
- [ ] Can I answer an interview question in English about cache-aside, invalidation ordering, or hot-key SWR?
- [ ] Can I invalidate every affected view (detail + recent-completed), not just one?
- [ ] Can I choose TTL + jitter for avalanche and single-flight for one hot key, and say why they differ?
- [ ] Can I recover an unknown cache-delete outcome with an Outbox intent + idempotent DEL, never a redo?
- [ ] Can I pick the correct rollback target (the cache contract) in the v2 incident without touching PostgreSQL truth or the Provider?
```

Preparation for Day40 (Redis Messaging and Queue Semantics): review this lesson's ownership boundary and the
`redis/redis-cache-consistency-design.md` artifact, then preview Lists / Pub-Sub / Streams as different
models, durable backlog vs no-replay, consumer groups / ack / redelivery, and at-most-once vs at-least-once.
Keep Redis transactions/Lua and full rate limiting (Day41) and SQLAlchemy/Alembic (Phase 4) out of scope.

---

Engineering Artifact: [projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md](../../projects/ai-backend-data-layer/redis/redis-cache-consistency-design.md)
