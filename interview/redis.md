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
AOF still loses writes in the fsync/rewrite window. Persistence shrinks the loss window and speeds restart; it
never confers ownership. Truth stays in PostgreSQL; large bytes in Object Storage.

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
