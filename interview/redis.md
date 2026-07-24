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
