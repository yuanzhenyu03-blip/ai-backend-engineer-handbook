# Redis Interview

## Purpose

Interview questions and model answers for Redis in backend systems.

## Sections

- Data Structures
- Caching
- Expiration
- Pub/Sub
- Queues
- Rate Limiting
- Production Operations

---

## Day38 Redis Foundations and Data Structures

Pair with [`cheat_sheets/redis.md`](../cheat_sheets/redis.md) and the
[Day38 lesson](../docs/redis/day38-redis-foundations-and-data-structures.md).

### Q1 — A Job-progress key is evicted while PostgreSQL says the Job is `running`. What does the API do?

Model answer:

Fall back to PostgreSQL. A missing Redis key is a cache-miss, not missing truth — `app.jobs` is the
authoritative lifecycle. Declaring the Job failed would invent a failure, and re-calling the Provider could
pay for a duplicate, side-effectful model call. Rebuild detailed progress only from durable evidence;
otherwise report that real-time progress is temporarily unavailable.

Student's actual answer (preserved verbatim):

> "回PostgreSQL 查询，直接判定job失败会造成用户二次发起provider调用。"

Assessment: Correct — names the fallback and the concrete business harm.

### Q2 — Someone wants the whole Job lifecycle in Redis with a 24-hour TTL. What breaks?

Model answer:

At hour 25 the key expires and the record — and whether the Job succeeded — is gone. TTL means a key is
allowed to disappear, which is exactly wrong for a system of record. Authoritative state lives in
PostgreSQL; Redis holds only a disposable projection.

Student's actual answer (preserved verbatim):

> "第25小时key实效了，查不到job的记录，也不知道是否成功。"

Assessment: Correct.

### Q3 — Progress view: Hash or JSON String, and why?

Model answer:

A Hash. Workers update different fields independently; a JSON String forces read-modify-write, so two Workers
each read the whole object and write it back, and one field update silently overwrites the other. A Hash
updates each field on its own, and `HINCRBY` bumps a counter atomically.

Student's actual answer (preserved): initially "不知道"; after learning, chose a Hash for the named mutable
progress fields.

Assessment: The honest starting point is fine; the derived answer (Hash, with the read-modify-write reason)
is correct.

### Q4 — Match a structure to each access pattern: recent 100 completions, unique reporting Workers, ordered UI activity, a request counter.

Model answer:

Sorted Set (unique members + timestamp score) for recent 100 completions; Set (unique, unordered) for
reporting Worker IDs — a membership view, not ownership; List (ordered, duplicates) for the UI activity
feed; String with `INCR` for the counter (a List would waste an element per request).

Student's actual answers (preserved verbatim):

> "我会选择Sorted Set，因为要求最近100个完成的就不能出现重复的，按时间从新到旧表示需排序。"

> "应该选set，不希望重复但是也没有要求排序。"

> "选择list。"

Assessment: Sorted Set / Set / List all correct; the counter was corrected from a List to a String.

### Q5 — Why does the tenant belong in the key, and when do you cut a `v2`?

Model answer:

Without `tenant:{tenant_id}` in the key, one tenant's cached data can be served to another — a cross-tenant
exposure. Cut a new version only for an incompatible change (different type, changed semantic, or changed
TTL contract); an additive optional field does not need a `v2`.

Student's actual answers (preserved verbatim):

> "会出现获取到其他租户的缓存信息。"

> "新建 v2 key，因为旧版需要与新版同时运行。"

Assessment: Tenant answer exactly right; versioning reasoning right, sharpened to the incompatible-change
rule.

### Q6 — `HSET` then `EXPIRE`, and the process crashes between them. And two Workers both bump `percent`?

Model answer:

The crash leaves a permanent key — the TTL was never set. Two Workers each reading `40` and writing `41`
lose one update, because single-command atomicity does not span two commands. Use `HINCRBY` for the counter;
atomic composition of several commands is Day41.

Student's actual answers (preserved verbatim):

> "会导致这条命令一直留在redis中。"

> "不能，因为单命令原子性只能做到一条命令的原子性，而两个work是不同的命令。"

Assessment: Both correct.

### Q7 — How would you configure Redis persistence, and does it make Redis safe as the source of truth?

Model answer:

Combining RDB and AOF is a reasonable operational choice — RDB alone can serve a stale snapshot and AOF alone
can grow an unbounded file — but neither makes Redis authoritative. RDB loses writes after the last snapshot;
AOF's potential loss window depends mainly on its fsync policy (plus OS/disk persistence and the failure type)
and does not guarantee zero loss, while AOF rewrite is log compaction with CPU/I/O/disk cost, not itself a
loss window. Persistence shrinks the recovery loss window and speeds restart; it never confers ownership. Truth stays in PostgreSQL; large bytes in Object Storage.

Student's actual answer (preserved verbatim):

> "RDB+AOF结合使用...避免使用单个的造成AOF生成的文件过大或者RDB使用的旧的数据。"

Assessment: The RDB+AOF combination and each single-mode failure are correct; the correction is that "AOF
recovers all lost data" is false — it is a loss-window trade-off, not ownership.

### Q8 — Redis is completely down. What happens to cached reads, and how do you protect PostgreSQL?

Model answer:

Reads fall back to PostgreSQL, but bounded — an uncapped fallback stampedes the database. Apply Day37
connection/timeout/concurrency budgets, shed or queue excess, and serve a truthful "temporarily
unavailable." Degrade latency, not correctness.

Student's actual answer (preserved verbatim):

> "不从redis读取进展状态，将traffic直接从postgresql读取持久化数据状态。"

Assessment: The fallback direction is correct; the bounding (rate limits / Day37 budgets so the fallback does
not stampede PostgreSQL) is the correction added in class.

### Q9 — Progress keys were shipped without `EXPIRE` and memory is climbing. First instinct is `FLUSHALL`. What's wrong, and what's the fix?

Model answer:

`FLUSHALL`/`FLUSHDB` wipes the shared keyspace across every tenant and key class, turning a leak into a
self-inflicted outage. Instead: ship the fix so writes set `EXPIRE` again, `SCAN` the leaked prefix
(`ai:tenant:*:job-progress:v1:*`, never `KEYS` on a hot server), set correct TTLs or delete prefix-scoped
keys only, and verify memory falls, safe-key eviction stops, and new keys carry a TTL. No Job truth was ever
at risk — the leaked keys are rebuildable projections.

Assessment: The exam is recognizing the shared-keyspace blast radius and choosing prefix-scoped cleanup over
a global flush.

---

## Day39 Redis Cache Design and Consistency

Pair with [`cheat_sheets/redis.md`](../cheat_sheets/redis.md) and the
[Day39 lesson](../docs/redis/day39-redis-cache-design-and-consistency.md).

### Q1 — PostgreSQL committed `succeeded` but Redis serves `running`. Which wins, and does a short TTL fix it?

Model answer:

PostgreSQL's committed state is authoritative; the cache is a projection allowed to lag. A short TTL only
bounds the stale lifetime — it is not synchronization and does not push the new state into Redis (and a very
short TTL raises PostgreSQL load). Durable changes need post-commit invalidation.

Student's actual answer (preserved verbatim):

> "API应该以postgresql持久化状态为准。TTL设置短，只能加快cache清理的过程，清理后也不是马上去数据库同步状态。"

Assessment: Correct, including that a short TTL bounds staleness rather than synchronizing.

### Q2 — Walk the cache-aside read and say what happens on a miss.

Model answer:

`GET` the key; on a hit return the cached view only if the endpoint tolerates staleness; on a miss read
PostgreSQL, return it, then best-effort repopulate Redis with a TTL. A cache write failure must never
invalidate an already-correct PostgreSQL response.

Student's actual answer (preserved verbatim):

> "从PostgreSQL数据库中加载数据并在redis填充缓存。"

Assessment: Correct miss path; the full contract adds hit-if-tolerable and best-effort repopulate.

### Q3 — Delete the cache before or after the PostgreSQL commit?

Model answer:

After. Pre-commit delete races: another request misses, reads the old `running` row, and re-caches it with a
fresh TTL before the commit. Commit first, then invalidate; a small stale window remains because the cache is
a view, not truth.

Student's actual answer (preserved verbatim):

> "提交后删除"

Assessment: Correct; the important addition is the pre-commit re-cache race that reverse ordering opens.

### Q4 — The Job status changed. Is invalidating the Job-detail cache enough?

Model answer:

No — invalidate every affected view. On `running -> succeeded`, invalidate both the Job-detail cache and the
tenant recent-completed-Jobs view; invalidating only the detail leaves the list inconsistent. Prefer deleting
affected keys after commit over directly writing guessed values.

Student's actual answer (preserved verbatim):

> "先更新A再，更新B，因为B的意思是最近完成的job。"

Assessment: Correct that there are two affected views; the correction is to invalidate-after-commit rather
than direct guessed updates.

### Q5 — Can the cache keep the same key when `progress` changes from `42` (0-100) to `0.42` (0-1)?

Model answer:

No — that is an incompatible representation change, so it needs a new versioned key (`v2`) while old and new
APIs coexist. An additive optional field would not require a new version.

Student's actual answer (preserved verbatim):

> "因为会造成兼容性问题。"

Assessment: Correct — identifies the compatibility break; the precision is incompatible-change-only versioning.

### Q6 — Many keys share one fixed TTL and expire together. What breaks, and what fixes it?

Model answer:

A cache avalanche — many distinct keys expire together and all fall back to PostgreSQL. TTL jitter distributes
expiry and fixes it. Single-flight protects one hot key after a miss; it cannot solve a million distinct keys
expiring together.

Student's actual answer (preserved verbatim):

> "会发生所有的cache会一起丢掉...需要用其中一个作为leader来请求，其他进行等待。"

Assessment: The avalanche is correct; the correction is jitter for synchronized expiry vs single-flight for
one hot key.

### Q7 — 50,000 requests miss one hot key. Serve them safely; what may a progress page return meanwhile?

Model answer:

Elect one single-flight leader to read PostgreSQL/rebuild; followers wait within a bounded deadline or take an
allowed stale value. On leader timeout use bounded retry + backoff + jitter, not a full fan-out. A progress
page may return the stale `running` view immediately (stale-while-revalidate) — but SWR is not allowed for
sensitive operations.

Student's actual answers (preserved verbatim):

> "会造成缓存雪崩PostgreSQL请求压力增大，连接池被耗尽，应该让其中一个请求负责回源和重建 cache。"

> "先立刻返回旧的running。"

Assessment: Both correct; the additions are the bounded deadline, no-full-fallback rule, and the SWR
sensitive-op boundary.

### Q8 — Classify `GET /progress` and `POST /cancel` as fail-open or fail-closed.

Model answer:

`GET /progress` may fail open (bounded SWR, short stale `running`). `POST /cancel` must fail closed on
PostgreSQL authorization plus a guarded state transition — a cache cannot authorize a cancel, and a Job that
already committed `succeeded` cannot be cancelled, so even a PostgreSQL pre-read is not a substitute for the
guarded write.

Student's actual answers (preserved verbatim):

> "A. B"

> "不能，POST /jobs/{job_id}/cancel有的job已经success，是无法进行cancel。"

Assessment: Correct classification and domain reasoning; the guarded-write point is the key production rule.

### Q9 — Random non-existent Job IDs keep missing the cache. What is it, and how do you protect PostgreSQL?

Model answer:

Cache penetration (attack or broken client). Use a short, tenant-scoped negative cache for "not found"; keep
it short-lived, invalidate it on successful Job creation, and never treat it as a security/authorization
decision.

Student's actual answer (preserved verbatim):

> "这个问题应该是负载攻击。可以把Job 不存在的结果短暂缓存。"

Assessment: Right instinct; sharpened from "load attack" to cache penetration with the short-TTL/creation-
invalidation constraints.

### Q10 — Hit ratio is 99% but a `succeeded` Job shows `running`. What does hit ratio prove, and can a hit overload you?

Model answer:

Hit ratio measures efficiency, not truth — and yes, a cache hit can overload Redis when 50,000 requests hit
one key/node/path. To catch a stale `succeeded`, measure correctness: commit→invalidation delay/failure/
backlog, cache age, stale-terminal rate, and sampled Redis-vs-PostgreSQL agreement.

Student's actual answers (preserved verbatim):

> (hot key) "不知道"

> (high hit ratio but stale) "miss ratio"

Assessment: Honest "don't know" on the hot key; the correction is that neither hit nor miss ratio measures
truth — freshness/agreement metrics do.

### Q11 — The cache `DEL` timed out after a `succeeded` commit. Most dangerous action, and the safe recovery?

Model answer:

Most dangerous: redoing the Job transition or re-calling the Provider. Safe recovery: record the invalidation
intent transactionally with the state change (Outbox) and have a Relay retry an idempotent `DEL`; TTL bounds
the residual stale window. Cache-delete idempotency is unlike Provider retries, which need a stable idempotency
key and Artifact reconciliation.

Student's actual answers (preserved verbatim):

> "最危险的操作动作是直接重新提交。手动删除。"

> "因为重新调用provider需要结合幂等key,防止二次调用。"

Assessment: Correct that resubmitting is the danger; "manual delete" is upgraded to the durable Outbox +
retryable idempotent `DEL`.

### Q12 — v2 cache deployed, PostgreSQL `succeeded`, invalidation Relay timed out, 50,000 users read v1 `running`. Roll back to v1?

Model answer:

No. v1 is stale too, and there is no evidence the v2 contract is faulty. Reconcile/retry invalidation, serve
bounded SWR/single-flight, and protect PostgreSQL first. Roll back the Redis v2 cache contract/traffic only if
evidence proves v2 misinterprets the data (e.g. `0.42` shown as `42%`), then invalidate v2 keys and rebuild
from PostgreSQL — never roll back committed PostgreSQL Job truth or rerun Provider work.

Student's actual answers (preserved verbatim):

> "先回滚到V1版本。"

> "Redis v2 cache contract，因为v2不兼容错误解释数据，PostgreSQL 的 Job state是权威持久化状态，provieder避免二次调用。"

Assessment: The student self-corrected from an automatic v1 rollback to rolling back only the cache contract,
naming PostgreSQL as authoritative and the Provider as not-to-be-recalled.

---

## Day40 Redis Messaging and Queue Semantics

Pair with [`cheat_sheets/redis.md`](../cheat_sheets/redis.md) and the
[Day40 lesson](../docs/redis/day40-redis-messaging-and-queue-semantics.md).

### Q1 — A Worker consumed a Stream message, may have done the work, and crashed before `XACK`. Is the Job done?

Model answer:

Unknown until reconciled. The entry is Pending in the Consumer Group's PEL and must remain recoverable via
Claim/redelivery. Redis cannot know whether the business effect happened; PostgreSQL Job/Attempt/Event/Outbox
records plus Provider reconciliation decide completion. `XACK` closes delivery for one group; it does not create
business truth.

Student's actual answer (preserved verbatim):

> "视为已处理，因为没有ACK确认，任务还在queue中。但是实际上已经处理结束了"

Assessment: the student spotted that the work may actually have finished; the correction is that a Pending entry
is "unknown," decided by durable state and reconciliation — not "already processed."

### Q2 — Before replaying a redelivered message, how do you avoid a duplicate Provider call?

Model answer:

Inspect durable PostgreSQL state (Attempt/Event) and the stable idempotency evidence, reconcile the real
outcome, and only then decide whether to repeat the side effect.

Student's actual answer (preserved verbatim):

> "检查postgresql，主要是查看attempt和event的状态，结合幂等键，防止二次调用provider"

Assessment: correct direction — durable state + stable idempotency before replaying a Provider side effect.

### Q3 — Why can't Pub/Sub be used for recoverable Job dispatch?

Model answer:

Pub/Sub is live broadcast with no durable backlog, ACK, PEL, Claim, or replay, so an offline or crashed
subscriber permanently misses the message. It is only for loss-tolerant live notifications; use Streams Consumer
Groups for recoverable dispatch.

Student's actual answer (preserved verbatim):

> "因为pub/sub只是做广播。并不负责对方是否收到，如果sub在pub发送消息之后，崩溃了没有收到消息，重新上线之后也不会找回pub发送的消息"

Assessment: correct — Pub/Sub has no durable backlog or replay for an offline/crashed subscriber.

### Q4 — What does ACKing immediately (before processing) cost you?

Model answer:

Early `XACK` removes the group's PEL recovery path, so a crash after ACK silently loses the Job — at-most-once.
Persist a durable, recoverable decision first, then `XACK`, for at-least-once with a recovery path.

Student's actual answer (preserved verbatim):

> "立刻XACK,redis内部就会删除work的PEL，这个时候崩溃了这条PEL就找不到了，就不会再有work执行这个job，属于at-most-once"

Assessment: correct — early ACK removes the Group recovery path and risks lost work.

### Q5 — Why prefer delayed ACK (possible redelivery) over early ACK?

Model answer:

Controlled duplicate delivery is recoverable — durable state + idempotency make a redelivered message safe —
whereas early ACK can lose a recoverable processing path, and if PostgreSQL never persisted the state, that row
is never updated again.

Student's actual answer (preserved verbatim):

> "因为重投可以通过持久化状态结合幂等键进行可控投递，而提前ACK意味PEL提前被redis内部移除。如果这个时候PostgreSQL的状态也没有写入，就代表这条数据库的状态再也不会更新"

Assessment: correct — controlled duplicate delivery is safer than losing a recoverable path.

### Q6 — Does Stream append order guarantee the order business effects complete under concurrent consumers?

Model answer:

No. Append order is transport order; concurrent consumers complete out of order. PostgreSQL guarded state
transitions and idempotency preserve business validity regardless of arrival order.

Student's actual answer (preserved verbatim):

> "不能保障"

Assessment: correct — transport order is not business-completion order.

### Q7 — A poison message keeps failing and holds a connection retrying. What do you do?

Model answer:

Contain through durable quarantine/dead-letter evidence, alert, repair the producer/contract, and controlled-
replay a corrected message; `XACK` the original only after quarantine evidence exists. Never silently delete a
failed Job message.

Student's actual answer (preserved verbatim):

> "会造成redis一直处于重试状态，一直占用连接。我觉得应该先contain，再删除"

Assessment: the "contain first" instinct is right; the correction is quarantine-then-ACK, never silent delete.

### Q8 — Is hitting the retry limit proof the error is permanent? And a fixed payload missing `tenant_id`?

Model answer:

No — a retry limit is a capacity/containment policy, not an error classifier. A fixed immutable payload missing
required `tenant_id` is a permanent message-contract failure: retrying the identical message can't repair it.
Repair the producer/contract and controlled-replay a corrected message.

Student's actual answers (preserved verbatim):

> "不能，因为有一个重试上限"

> "瞬时错误，我会修复后重试"

Assessment: the retry-limit answer is correct; the missing-field case was corrected from "transient" to a
permanent contract failure that cannot be retried into success.

### Q9 — What does an unsafe Stream trim destroy?

Model answer:

Claim/redelivery/replay capability — trimming Pending entries or recovery/quarantine evidence deletes exactly
what recovery depends on. Trimming is a retention/capacity contract, not memory cleanup.

Student's actual answer (preserved verbatim):

> "破坏重放能力"

Assessment: correct — unsafe trim destroys Claim/redelivery/replay evidence.

### Q10 — Why isn't a persisted List a durable work queue equal to a Stream?

Model answer:

A List may be persisted, but it lacks native Consumer Group ownership, a PEL, ACK, Claim, and redelivery
lifecycle — persistence is not a consumer recovery lifecycle. Streams add those semantics; don't hand-build a
Celery replacement from raw Lists/Streams.

Student's actual answer (preserved verbatim):

> "list缺少streams持久化保存信息的机制"

Assessment: correct gap; the precision is that Lists may persist — the missing piece is the recovery lifecycle.

### Q11 — What belongs in a Stream payload when a Job produces a 300 MB PDF?

Model answer:

Small references only (`tenant_id`, `job_id`, `event_id`, trace). Object Storage owns the large bytes and
PostgreSQL owns the durable references/provenance; large payloads in messages inflate memory, replication, and
redelivery cost.

Student's actual answer (preserved verbatim):

> "object storage保存大文档，stream保存大文档会造成内存压力增大"

Assessment: correct large-byte ownership boundary.

### Q12 — Should Job execution and completion notification share one stream/group, and what actually gates the completion email?

Model answer:

No — and separate groups alone are not the real fix. Within one group a message goes to one consumer, so a
shared group would let one effect consume the other's deliveries; separate groups only mean both could *receive*
the same entry. The deeper issue is lifecycle: a `job-dispatch` event is emitted at Accept, when the Job is not
finished, so a completion email must not be derived from it. Model them as distinct committed events published
by the Relay from PostgreSQL Outbox intents: the Accept transaction commits a `job-dispatch` intent →
`ai:stream:job-dispatch:v1` → `g:job-exec`; the Complete transaction commits a `job.completed` intent →
`ai:stream:job-events:v1` (or one shared event stream with an explicit `event_type`) → `g:notify-delivery`. The
completion email is driven only by a committed `job.completed` event — the student's "用数据库中持久化的事实拦住"
— never by a dispatch entry.

Student's actual answer (preserved verbatim):

> "会发生一个work已经发送用户通知的服务，而执行 Job 的 Worker还在处理。应该用数据库中持久化的事实拦住。"

Assessment: the race and the "gate it with the committed database fact" instinct are exactly right; the
structural fix is distinct committed lifecycle events (dispatch vs job.completed) on distinct streams/groups, not
merely separate groups on one dispatch stream.

### Q13 — Can you decide "email already sent?" from the Job's Attempt/Event and one `job_id` key?

Model answer:

No — a Job Attempt/Event does not prove an email was delivered, and one `job_id` cannot key completion, failure,
and admin notifications because they are separate effects. The completion email is triggered only by a committed
`job.completed` event (from the Complete transaction's Outbox intent, consumed by `g:notify-delivery`), and it
uses its own delivery-specific identity, e.g. `job:{job_id}:notification:completion:v1`.

Student's actual answer (preserved verbatim):

> "根据数据库持久化attempt与event结合幂等键判断是否已经发送邮件"

Assessment: checking durable state is the right reflex; the correction is a dedicated per-effect notification
delivery identity/record.

### Q14 — English interview: why can't Redis Streams alone give exactly-once?

Model answer:

Because exactly-once would require Redis ACK, the PostgreSQL commit, and the external Provider call to succeed or
fail together, which Redis cannot coordinate. Redis gives at-least-once with Consumer Groups; exactly-once is
engineered with durable state, guarded transitions, per-side-effect idempotency, and reconciliation.

Assessment: names the three-way boundary and the at-least-once + idempotency resolution.

---

## Day41 Redis Coordination and Production Safety

Pair with [`cheat_sheets/redis.md`](../cheat_sheets/redis.md) and the
[Day41 lesson](../docs/redis/day41-redis-coordination-and-production-safety.md).

### Q1 — Two API Pods both read the rate count as 59 and both admit. What property is missing?

Model answer:

Atomicity, not necessarily a lock. The bug is a `read → check → write` split across Pods. Use an atomic
read-modify-write — a short Lua that reads, checks the limit, increments only when allowed, and sets the TTL as
one step. A distributed lock would work but adds its own expiry/safe-release/recovery risks.

Student's actual answer (preserved verbatim):

> "缺少并发控制的锁"

Assessment: reasonable lock instinct; the correction is that the missing property is atomic read-modify-write.

### Q2 — Is `INCR` then `DECR`-on-rejection a safe way to enforce the limit?

Model answer:

No — a crash or interleave between `INCR` and `DECR` leaves the counter inflated; a rejected request must not
depend on a later compensating decrement. Keep check + allowed increment + TTL in one atomic Lua step.

Student's actual answer (preserved verbatim):

> "先判断是否大于60，如果大于60计数-1返回拒绝"

Assessment: the compensation idea is the misconception; the fix is one atomic server-side operation.

### Q3 — Redis admitted the request but the PostgreSQL Accept failed. Roll the counter back?

Model answer:

No. The counter is an allowed attempt, not a created Job; the TTL resets the window, and compensating adds a
second Redis/PostgreSQL uncertainty boundary. PostgreSQL Job + Outbox is the durable acceptance truth.

Student's actual answer (preserved verbatim):

> "不需要回退。而且每分钟60次还设置了TTL，到时间了就会重新开始一个新的限流计数"

Assessment: correct — admission is not durable success, so don't couple the counter to durable state.

### Q4 — Does a clock-aligned fixed window allow a boundary burst, and which algorithm for expensive AI Jobs?

Model answer:

Yes — 60 at `12:00:59` plus 60 at `12:01:00` is 120 in about a second. A sliding window prevents that and is
right for expensive Job creation (smooth/fair, costlier); a first-write TTL is request-anchored with different
semantics; a token bucket allows a bounded burst.

Student's actual answers (preserved verbatim):

> "不会允许，因为12:01:59才会刷新，而这里只是经过了一秒又发了60次"

> "我更倾向于滑动窗口"

Assessment: the sliding-window preference is right; the correction is that a clock-aligned fixed window *does*
permit the boundary burst.

### Q5 — Token bucket capacity 10, refill 1/s: is the 11th request 0.2s after ten tokens are consumed allowed?

Model answer:

No — about zero tokens are available 0.2s later, so it's rejected and can be given a retry estimate (~0.8s to the
next token). Capacity permits the burst; refill bounds the long-run average.

Student's actual answers (preserved verbatim):

> "令牌桶"

> "无法请求"

Assessment: correct algorithm choice and rejection.

### Q6 — How do you de-duplicate a timed-out `POST /jobs` retry, and is a Redis lock the authority?

Model answer:

Use a stable client idempotency key plus a PostgreSQL `(tenant_id, idempotency_key)` uniqueness boundary to
create-or-return the same Job + Outbox intent and replay the same `202 + job_id`. Attempt/Event may not exist
before a Worker starts, so they can't dedup a first POST. A Redis lock only reduces optional duplicate
preliminary work; the PostgreSQL unique constraint is the final authority.

Student's actual answers (preserved verbatim):

> "根据数据库持久化事实attempt、event、outbox intent来判断"

> "需要，因为redis锁可以保护多个请求的并发"

Assessment: durable-fact reflex is right but Worker facts may not exist; the DB unique constraint (not the Redis
lock) is the authority.

### Q7 — Worker A holds a 30s lease, pauses at 29s, expires, B takes over, A resumes. Can a lease alone prevent both calling the Provider?

Model answer:

No. Lease expiry permits reassignment; it doesn't prove A died before external work and can't stop a paused A or
its in-flight Provider call. External-effect safety comes from stable Provider idempotency + Artifact
reconciliation, and durable-write safety from the PostgreSQL guard.

Student's actual answer (preserved verbatim):

> "不能"

Assessment: correct — a lease coordinates the next owner, not external work.

### Q8 — Why is `DEL lock_key` after expiry unsafe, and what replaces it?

Model answer:

Old A can delete new B's lease, letting a third Worker enter. Replace with atomic compare-and-delete (Lua):
delete only when the stored token equals the caller's token. Safe release still does not stop A's already-started
Provider call.

Student's actual answers (preserved verbatim):

> "会导致下一个work再次进入到A的业务内"

> "不能，锁本身只能保证下一个work不会执行当前work中的任务，并不会在当前锁过期后，外部的业务就停止了"

Assessment: correct on both the unsafe-delete hazard and the limit of safe release.

### Q9 — Why can't a UUID lease token act as a fencing token, and how does PostgreSQL reject a stale owner?

Model answer:

A UUID is unordered, so even a cooperating downstream can't tell newer from older. A fencing token is a
monotonically increasing generation whose correctness must not depend on rollback-able Redis — it is advanced and
persisted in a PostgreSQL claim/takeover transaction (never a Redis `INCR`, which a failover could hand out
smaller or duplicate). Generically, a downstream accepts a write only when `last_accepted_fence < incoming_fence`
and then persists it. For the Job Complete predicate specifically, the guard uses equality: `running` + current
lease token + `lease_expires_at > now()` + `fencing_generation` = the current persisted generation, so a stale
owner's old generation can't equal the current one and is rejected.

Student's actual answers (preserved verbatim):

> "因为下游的provider不能区分lease_token的区别"

> "通过比较fencing token,如果新加入的大于前一个就允许，如果小于就拒绝"

Assessment: the fencing comparison (newer accepted, older rejected) is the right generic rule; the corrections are
that the UUID's lack of ordering (not just the Provider) is why it can't fence, that the generation must be minted
durably in PostgreSQL (not a losable Redis value), and that the Job Complete guard uses equality with the current
persisted generation.

### Q10 — Redis fails over and loses recent counters. Does a low count mean the tenant is under limit? And should coordination state share cache capacity?

Model answer:

No — a low/missing counter is degraded protection, not "under limit"; a missing counter can temporarily allow
extra requests and raise pressure. RDB loses post-snapshot changes, AOF loss depends on fsync, and a promoted
replica can lack recent writes. Isolate coordination state from LRU-evictable cache (separate instance/cluster)
with explicit memory/TTL/eviction/alerts.

Student's actual answers (preserved verbatim):

> "不说明，应该是为了防止在这期间无限制调用"

> "可能多放行一部分请求，造成段短时间请求压力增大"

> "因为复制的是之前的的限流计数"

> "应该分开放在不同实例，防止缓存挤掉保护数据"

Assessment: correct — treat loss as monitored protection degradation and isolate the guardrail from the cache.

### Q11 — Is private-network placement enough Redis security, what ACL scope for a rate-limit client, and does managed Redis remove responsibility?

Model answer:

Private network is necessary but insufficient; add auth, ACLs, TLS, dangerous-command restriction, audit, and
monitoring. Scope the rate-limit client to its required commands and the `ratelimit:*` prefix — no arbitrary
keys, `FLUSHALL`, or `CONFIG`. Managed Redis runs infrastructure but does not transfer business responsibility
(semantics, capacity/eviction, ACL/TLS, monitoring, loss windows, incidents stay the team's).

Student's actual answers (preserved verbatim):

> "不能"

> "不能，对待高风险命令应该严格限制，只能在规定范围的key前缀进行读写权限"

> "不能,因为实际业务还是需要自运维进行配置"

Assessment: correct on all three — layered least-privilege security and retained business responsibility.

### Q12 — Redis fails over (lost counters) while A pauses mid-Provider-call, its lease expires, and B gets a new lease. Contain it.

Model answer:

Fail closed on new expensive Job admission; do not mass-restart Workers (it interrupts in-flight calls); use
bounded backoff on new Redis-dependent actions and drain/reconcile after recovery. B must not call the Provider on
the fresh lease alone — reconcile PostgreSQL Job/Attempt/Event/Outbox + stable Provider idempotency + the
deterministic Artifact; guard final writes by ownership + fencing. Treat lost counters as monitored protection
degradation. Contain new admissions/coordination on unhealthy Redis; don't "roll back" Provider calls.

Student's actual answers (preserved verbatim):

> "fail-closed，因为主要是post一类的请求，需要修改持久化数据状态。"

> "不能，要先根据数据库持久化事实结合idempotency进行判断是否要再次调用，以及如果A恢复后可能会继续执行业务"

> "不会，因为还是要与数据库持久化事实结合idemotency key进行判断"

> "eviction、以及是否限流器失去了作用，请求增大"

Assessment: correct throughout — fail-closed admission, no mass restart, reconcile durable facts, monitor
degradation.

### Q13 — (Beginner, English) Why can `GET → check → INCR` race, and what is safer?

Student answer (verbatim):

> because these comman in a same Atomicity transaction ,use lua script instead of comman.

Strong answer:

> "`GET`, checking the value, and `INCR` are separate operations. Two API instances can read the same old value
> before either increments, so both may allow the request. A safer approach is a short Lua script that reads,
> checks, increments, and sets the TTL atomically."

Assessment: correct tool (Lua); the strong answer explains the read-before-increment race.

### Q14 — (Intermediate, English) Lease token vs fencing token; why isn't a lease token enough for a paused worker?

Student answer (verbatim):

> lease token just avoid a worker running stop,lease token expire.other worker continue  working.the worker wake up continue running.lease token can't continue beacuse lease token different.but the real bussiness can't stop.fencing token store database,the next fencing token must more than before fencing token

Strong answer:

> "A lease token is an opaque ownership identifier. It helps a worker renew or safely release its current lease,
> but it cannot stop a paused worker after the lease expires. A fencing token is a monotonically increasing
> ownership generation. The downstream durable store records the newest token and rejects writes from older
> tokens, so a stale worker cannot overwrite newer work. External providers may not support fencing, so they
> still need stable idempotency keys and reconciliation."

Assessment: the student had the core (lease can't stop the business; fencing is stored + monotonic); the strong
answer adds opaque-vs-ordered and the Provider-idempotency boundary.

### Q15 — (Senior, English) Contain a failover that lost counters plus a paused-A / new-B lease conflict.

Student answer (verbatim):

> use the durable database truth,such as event\attempt\oubox intex and idepmotency key reconcil artifact.

Strong answer:

> "First, I would fail closed for new expensive Job admission while the Redis rate limiter is unavailable, and I
> would not restart all workers because that could interrupt in-flight Provider calls. After failover, I would
> treat lost rate-limit counters as a temporary protection degradation and monitor evictions, memory pressure,
> failover, admission volume, and reject rate. Worker B must not call the Provider only because it acquired a new
> Redis lease. It should reconcile PostgreSQL durable facts such as the Job, Attempt, Event, and Outbox records,
> check the stable Provider idempotency key, and verify the deterministic Artifact. A paused Worker A may resume,
> so final PostgreSQL writes must be guarded by the current lease token, an unexpired lease, and equality with the current persisted fencing generation (minted durably at takeover), while the Provider side
> effect is protected by its own idempotency key. Redis coordinates work, but PostgreSQL remains the durable
> business authority."

Assessment: the student named the durable-facts + idempotency + Artifact foundation; the strong answer adds
fail-closed admission, no mass restart, degradation monitoring, and the ownership/fencing guard.

---

## Day42 Backend Data Design Capstone — Phase 3 System-Design Interview

Cross-boundary Phase 3 capstone (PostgreSQL + Redis + Object Storage). Pair with
[`cheat_sheets/redis.md`](../cheat_sheets/redis.md) (Day42), the
[Day42 lesson](../docs/redis/day42-backend-data-design-capstone.md), and the
[Day42 capstone design](../projects/ai-backend-data-layer/capstone-backend-data-design.md).

### Q1 (Beginner) — What owns durable truth in this AI backend, and what is Redis for?

Model answer:

PostgreSQL owns durable truth: Job identity/status, tenant ownership, the API idempotency uniqueness, the Outbox
intent, Attempt/Event history, the fencing generation, and references to Object Storage artifacts. Object
Storage holds the large document and result bytes. Redis is transient coordination (cache, queue messages,
rate-limit counters, short leases) and is losable on eviction/failover, so it never proves a Job was accepted or
completed.

### Q2 (Beginner) — What must be durable before you return `202`?

Model answer:

Job + `(tenant_id, idempotency_key)` uniqueness + the Outbox dispatch intent, committed in one PostgreSQL
transaction. Attempt, Event, lease token, and fencing generation are not required at `202` — they appear at
claim/takeover.

Student's actual answer (preserved verbatim):

> "Postgresql持有attempt、event、outbox intent、stable idepmotency key、fencing token"

Assessment: correct list of durable PostgreSQL-owned facts; the interview refinement is that only Job +
idempotency uniqueness + Outbox are required *at acceptance*.

### Q3 (Intermediate) — A Relay re-published a message so a Worker got it twice. How do you stay correct?

Model answer:

At-least-once duplicate delivery is expected; do not reject the delivery. Reject the duplicate business effect
with a PostgreSQL guarded transition (only one `queued -> running` succeeds) plus idempotency; a Redis processed
marker is an optional optimization, never the authority.

Student's actual answers (preserved verbatim):

> "重复投递应该使用拒绝"

> "依赖 PostgreSQL 的 guarded 状态转换，redis不是持久化数据事实"

Assessment: the second answer corrects the first — guard the effect, not the delivery.

### Q4 (Intermediate) — The result Artifact is in Object Storage. Is the Job done?

Model answer:

No. Artifact existence alone is insufficient. Completion is a short guarded transaction (record Artifact
reference, finish the Attempt, `running -> succeeded`, append the Event) after verifying Artifact identity/
integrity/ownership, current ownership + fencing equality, and Provider/result evidence. If the Object Storage
write succeeded but the completion rolled back, reconcile — never blindly delete the Artifact or re-call the
Provider.

Student's actual answers (preserved verbatim):

> (is Artifact existence enough?) "不能"

> "应该根据idepmotency key在provider查询结果reconcile artifact"

Assessment: correct — verify + guarded completion; Artifact presence is not success.

### Q5 (Intermediate) — Degraded modes: Redis, PostgreSQL, and input Object Storage each unavailable.

Model answer:

Redis unhealthy → fail closed on new expensive admission, do not read a low counter as headroom, no mass
restart, bounded backoff, drain in-flight work. PostgreSQL down → do not accept new `POST /jobs` (acceptance
atomicity is PostgreSQL-only), preserve external evidence, reconcile after recovery. Input Object Storage down /
upload unverifiable → fail closed that admission only, not unrelated endpoints or the whole container.

Student's actual answers (preserved verbatim):

> "不能，因为postgresql的持久化事实是唯一事实来源"

> "contain现有结果拒绝新的job admission，等待数据库恢复后，再运行原子事务提交数据库"

> "不能接受，应该container停止接收新的job admission。"

Assessment: correct posture; the correction is to scope the Object Storage fail-closed to the affected admission
path, not the whole container.

### Q6 (Intermediate) — How do you keep tenants isolated in reads and relationships?

Model answer:

Use the authenticated tenant predicate plus the Job ID on every read — a globally unique `job_id` still leaks if
another tenant learns it and the query filters by `job_id` alone. Prevent cross-tenant links with composite
tenant-aware foreign keys, e.g. `job_documents(tenant_id, job_id, document_id)` referencing both `(tenant_id,
job_id)` and `(tenant_id, document_id)`.

Student's actual answers (preserved verbatim):

> "必须包含租户id"

> "不安全，一个job_id可能有多个租户"

> "使用unique约束job_id,tenant_id,document_id为唯一组合"

Assessment: right conclusions; the reasoning refinement is that the leak is A learning B's unique UUID, and that
composite FKs (not mere unique association) prevent cross-tenant links.

### Q7 (Senior) — Walk through completing a Job after Worker A paused mid-Provider-call, its lease expired, and Worker B took over and found the Artifact.

Model answer:

A fresh lease is permission to reconcile, not to repeat expensive work. B must not call the Provider just
because it holds the lease, and must not treat the Artifact's existence as success. B reconciles Job / Attempt /
Event / Outbox / stable Provider idempotency and verifies the deterministic Artifact's identity/integrity/
ownership. Completion is a short guarded transaction guarded by `running` + current lease token + unexpired
lease + equality with the current persisted fencing generation, so A's stale completion (older generation)
fails the guard. Ensure the legacy completion path cannot bypass the guard (drain/upgrade old Workers); a fence
only protects writers that verify it.

Student's actual answer (preserved verbatim):

> "contain先停止旧work接新的job admission，对旧的在运行的work进行brain，确认旧work无法再按照旧路径写入， B先对账 Job / Attempt / Provider idempotency / Artifact，再决定是否调用 Provider 或提交完成事务绝对不能重新调用proveider,绝对不能把artifact存在替代ownership的检查。"

Assessment: complete and correct — contain, reconcile, guarded completion, and the two absolutes (never blind
re-call, never Artifact-as-ownership).

### Q8 (Senior) — Roll out the `current_fencing_generation` with old Workers still running.

Model answer:

Expand (add nullable) → compatible deploy (tolerate NULL) → backfill → validate all running Jobs/completion
paths → switch (claim/takeover writes a strictly greater durable generation; enforce the guard) → contract. Do
not shorten the lease to "force" takeover and do not hand the old Worker a smaller generation — expiry never
stops a paused old Worker and old code may bypass the fence. Drain/upgrade old Workers or enforce the guard on
every durable completion path; Provider effects still rely on idempotency + reconciliation.

Student's actual answers (preserved verbatim):

> "先nullable新字段保持新旧版本兼容性，切换traffic让新的job都带上这个字段，对还在运行的旧work brain"

> "lease token的过期时间短，让新worker可以接管。之后新worker获得fencing generation，然后给旧work一个小于或等于新work的generation，下游就会拒绝旧work"

Assessment: the Expand-first instinct is right; the correction is that lease-shortening + a smaller generation
cannot stop old code — drain/upgrade or enforce the guard universally.

### Q9 (Senior) — How do you justify a proposed index, and is `EXPLAIN ANALYZE` production validation?

Model answer:

In a disposable isolated environment collect representative schema/index/data/params, run `EXPLAIN ANALYZE`,
compare actual vs estimated rows, timing, and buffers before/after the index. That is disposable runtime
evidence, not production validation — real deployment and telemetry are a separate, later tier.

Student's actual answers (preserved verbatim):

> "在隔离环境使用explan analyze"

> (is that production validation?) "不能，因为还需要真实环境迁移后测试"

Assessment: correct on both — measure in a disposable environment and label the evidence tier honestly.

### Final Chinese synthesis (preserved verbatim)

> PostgreSQL owns durable business facts; Redis transports information and stores cache/counters; Object Storage
> stores documents and large binary files; Job + stable idempotency key + Outbox intent commit before 202; Relay
> scans unpublished Outbox; Worker updates Attempt/Event/Job; recovery uses Attempt/Event/Outbox/idempotency/
> Artifact; PostgreSQL durable facts are the single source of truth.

Validation: CONCEPTUAL / STATICALLY REVIEWED only — RUNTIME NOT RUN, PRODUCTION NOT VALIDATED. No PostgreSQL/
Redis/Object Storage/Provider/Celery/FastAPI/migration/`EXPLAIN ANALYZE` was executed. SQLAlchemy/Alembic are
Phase 4.
