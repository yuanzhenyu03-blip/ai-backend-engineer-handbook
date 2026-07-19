# PostgreSQL Interview

## Purpose

Interview questions and model answers for PostgreSQL backend engineering.

## Sections

- Schema Design
- Indexes
- Transactions
- Query Optimization
- Migrations
- Connection Pooling
- Production Operations

---

# Day29 PostgreSQL Foundations and Durable Relational State Questions

From the Day29 lesson: durable relational state before `202`, the PostgreSQL/session boundary, types and
defaults, NULL vs NOT NULL, row identity vs request identity, `timestamptz`, validation levels, and
guarded data repair.

Lesson: `docs/postgresql/day29-postgresql-foundations-and-durable-relational-state.md`

## Beginner

### 1. Why must FastAPI persist a Job row in PostgreSQL before returning 202 Accepted?

Question:

Why must FastAPI persist a Job row in PostgreSQL before returning `202 Accepted`?

中文解析:

`202` 是一个**持久化的业务承诺**，不是"稍后再写"的信号。行必须先写入并提交，然后才返回 `202`。如果 API Pod 在响应后立刻被替换（Kubernetes 滚动更新/崩溃），内存里的 Job 就消失了，客户端手里的 `job_id` 指向不存在的东西。写在前面，系统之后仍能找到、恢复并处理该 Job。但要注意：仅有数据库行**并不能防止重复执行**，幂等控制仍然必要。

Student's actual attempt (preserved):

> "because the durable state in postgresql,it help work to avoid repeate run job."

Interview Review: "durable state" 方向正确，但数据库行本身不阻止重复执行；这是两件事。

Standard Answer:

FastAPI must persist the Job in PostgreSQL before returning 202 Accepted because 202 represents a
durable business commitment. If the API Pod crashes afterward, the system can still find, recover, and
process the Job. The database row alone does not prevent duplicate execution, so idempotency controls are
still required.

Follow-up Question:

What does `NOT NULL` on `job_status` actually guarantee?

## Intermediate

### 1. Primary key vs idempotency key in the Job model.

Question:

What is the difference between a primary key and an idempotency key in the Job model?

中文解析:

主键标识**一行**，防止重复的**键值**；在本 schema 中由 PostgreSQL 以 UUID 生成。幂等键标识**一次业务请求**，通常由客户端提供或应用派生。客户端重试时，系统用幂等键返回已存在的 Job，而不是再建一个。注意"由谁生成"不是定义本身；用 "unique identifier" 而不是 "certification"。请求幂等与 provider 幂等是两个不同的作用域。

Student's actual attempt (preserved):

> "the primary key is produced by postgresql,and it is a only job certification. an indempotency key is produced by provider."

Interview Review: 生成方不是定义；用 "unique identifier" 而非 "certification"；请求幂等键通常来自客户端/应用，provider 幂等是另一个作用域。

Standard Answer:

A primary key uniquely identifies one Job row in PostgreSQL. In our schema, PostgreSQL generates it as a
UUID. An idempotency key identifies one business request and is usually supplied by the client or derived
by the application. If the client retries the same request, the system uses the idempotency key to return
the existing Job instead of creating another one.

Follow-up Question:

Why is a read-before-write check not enough to enforce it?

### 2. What does `NOT NULL` not protect, and why did `banana` succeed?

Question:

`job_status text NOT NULL DEFAULT 'queued'` — what does that guarantee, and what does it not?

中文解析:

`NOT NULL` 只拒绝 SQL `NULL`。它**接受空字符串和任意文本**——课堂运行时证据显示 `''` 和 `'banana'` 都被成功写入。要保证状态取值合法，需要 `CHECK` 或枚举式约束（Day31）。这正是 Day29 的核心风险：**持久化不等于正确性**——拼错的 `queud` 会被永久保存，而 worker 只认 `queued`，于是这个 Job 永远不会被认领。

Standard Answer:

`NOT NULL` only rejects SQL NULL. It still accepts an empty string and arbitrary text — at runtime both
`''` and `'banana'` were accepted. Guaranteeing a valid status requires a CHECK constraint or an enum-style
rule, which is later work. That is why durability is not integrity: a misspelled `queud` row is stored
forever and never claimed by a worker.

Follow-up Question:

The API already wrote 100 `queud` rows. Is rolling back the API enough?

## Senior

### 1. Lost 202 + client retry: prevent a duplicate Job, and name the Day29 limitation.

Question:

PostgreSQL creates a Job, the `202` response is lost, and the client retries. How do you prevent a
duplicate Job, and what limitation remains in the Day29 schema?

中文解析:

客户端重试时应带**同一个幂等键**；把该键与 Job 一起存储，并用 PostgreSQL **唯一约束**强制。要用**原子 insert/upsert**，而不是先读后写——两个并发请求可能都看到键不存在，于是都插入。遇到冲突的那个请求，在校验请求负载一致后返回**已存在的 Job ID**。局限：Day29 的 schema **还没有幂等键，也没有唯一规则**，所以即使每行都有唯一主键，它仍然无法阻止重复的业务 Job（Day31 约束 + Day34 并发）。

Student's actual attempts (preserved):

> "client produce idempotency key"

> "我忘了"

Teaching note: after two attempts the complete answer was taught directly.

Standard Answer:

The client should provide the same idempotency key when it retries the request. I would store that key
with the Job and enforce it with a PostgreSQL unique constraint. I would use an atomic insert or upsert
instead of relying on a separate read-before-write check, because two concurrent requests can both observe
that the key is missing. The request that encounters the conflict should return the existing Job ID after
verifying that the request payload matches. Our current Day29 schema does not yet contain an idempotency
key or a uniqueness rule, so it cannot prevent duplicate business Jobs even though every row has a unique
primary key.

Follow-up Question:

Which validation level have you actually reached if the DDL ran successfully on your laptop?

## Common Weak vs Strong Answer (Day29)

```text
Weak:   "PostgreSQL creates the job_id after we return 202."
Strong: "The Job row is written and committed BEFORE 202; 202 acknowledges a commitment that already
        exists durably, so a Pod restart cannot lose it."

Weak:   "psql connects to the app schema."
Strong: "psql connects to one database; the schema is resolved by a qualified name like app.jobs or by
        search_path. `public` is just the default namespace."

Weak:   "NOT NULL makes the status valid."
Strong: "NOT NULL rejects NULL only; '' and 'banana' still pass. Valid states need a CHECK/enum rule."

Weak:   "We rolled the API back, so the bad rows are fixed."
Strong: "Code rollback stops future bad writes only. I contain, identify the exact affected set, run a
        guarded UPDATE, capture the row count and RETURNING as evidence, then verify workers can claim
        the Jobs again."

Weak:   "The schema ran locally, so it's production ready."
Strong: "Executed DDL proves acceptance in that PostgreSQL version. It is not application integration
        and not production evidence; a process restart proves process-lifecycle persistence only."
```
