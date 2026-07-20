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

---

# Day30 SQL Data Manipulation and Query Fundamentals Questions

From the Day30 lesson: deterministic reads, NULL/three-valued logic, parameterized SQL and the injection
boundary, `WHERE` as the modification boundary, guarded transitions, affected-row evidence, lost updates,
and incident recovery.

Lesson: `docs/postgresql/day30-sql-data-manipulation-and-query-fundamentals.md`

## Beginner

### 1. Why does `WHERE` matter in `UPDATE`/`DELETE`, and how do you verify what happened?

Question:

Why does the `WHERE` clause matter in an `UPDATE` or `DELETE`, and how do you verify what happened?

中文解析:

`WHERE` 定义了修改边界——它决定了究竟哪些行被改变。在事务提交前，写错的语句还可以 `ROLLBACK` 撤销（完整事务边界属于 Day33）；但**一旦 COMMIT，就没有自动撤销**，而回滚应用代码只能阻止后续的错误写入，并不会修复已提交的行——只能做守卫式的数据修复。验证方式有两个：驱动返回的**受影响行数**，以及 `RETURNING` 返回的**实际行**。对主键条件的状态转换，契约通常是"恰好 1 行"；如果实际行数与预期不符（例如本课事故中预期 1 行却影响了 842 行），必须当作失败处理，不能上报成功。注意 `RETURNING` 返回的是行本身，不是计数。

Student's actual attempt (preserved):

> "the where define bondary of modify,because the affected rows is durable state and backend engineer could compare the diffrent between expended result and fact result by check the affect rows."

Interview Review: 概念正确（边界 + 用受影响行数比对预期）。英文需修正：`bondary` → boundary，`diffrent` → difference，`expended` → expected，`affect rows` → affected rows。

Standard Answer:

The `WHERE` clause defines the boundary of the modification: it decides exactly which rows are changed.
Because those changes are durable, I verify the result by checking the number of affected rows and by
using `RETURNING` to see the rows the statement actually produced. If the affected-row count does not
match what I expected — for example one row for a primary-key transition — I treat it as a failure and do
not report success.

Follow-up Question:

What does zero affected rows tell you about a guarded transition?

## Intermediate

### 1. What does parameterized SQL protect against, and what does it not solve?

Question:

What does parameterized SQL protect against, and what does it **not** solve?

中文解析:

参数化让 SQL 结构固定、值单独绑定，值永远不会被重新解析为 SQL 结构——这就是注入边界。即使 JSON 里含引号或 `DELETE FROM app.jobs` 文本，它仍只是数据。但它**不解决**：业务规则校验、鉴权与租户归属、逻辑错误与并发错误。另外参数只能绑定**值**，不能绑定表名/列名/`ASC|DESC`，动态标识符必须用严格白名单。占位符写法因驱动而异（asyncpg `$1`、psycopg `%s`、SQLAlchemy 命名绑定），不变的是代码与数据分离——绝不能用 f-string 拼接客户端输入。

Student's actual attempt (preserved):

> "it help to avoid affect use sql injection and parameterized SQL is bonded values,it can not effect the structure of sql.it also can resolve these problems,for example,parameterized sql can't constrait input"

Interview Review: 核心正确（绑定值不改变 SQL 结构 = 注入边界）；最后一句表达不清但方向对（不能约束输入）。

Standard Answer:

Parameterized SQL keeps the statement structure fixed and sends the client values separately, so a value
is never re-parsed as SQL. That closes the injection boundary. It does not validate business rules,
authorize the request, enforce tenant ownership, or prevent logical and concurrency bugs. Parameters also
bind values only — table names, column names, and sort direction need a strict allowlist instead.

Follow-up Question:

Two workers both read `attempt_count = 2` and both write 3. What happened, and how do you fix it without
a lock?

### 2. Why do rows disappear from `error_message <> 'timeout'`?

Question:

An operations query filters `WHERE error_message <> 'timeout'` but Jobs with no error are missing. Why?

中文解析:

SQL 是三值逻辑。`NULL <> 'timeout'` 的结果是 `UNKNOWN`，而 `WHERE` 只保留 `TRUE`，`FALSE` 和 `UNKNOWN` 都会被过滤掉，所以"没有错误"的行全部消失。要显式包含它们：`WHERE error_message IS NULL OR error_message <> 'timeout'`；PostgreSQL 的 `IS DISTINCT FROM 'timeout'` 是 NULL 安全的等价写法，但更容易被误写反（本课的状态转换守卫就踩过这个坑）。另外 `<>` 不是只比较文本，它适用于任何可比较类型。

Standard Answer:

SQL uses three-valued logic. Comparing NULL with anything yields UNKNOWN, and `WHERE` keeps only TRUE, so
rows whose `error_message` is NULL are filtered out along with the FALSE rows. To include them I write
`WHERE error_message IS NULL OR error_message <> 'timeout'`, or use the NULL-safe
`IS DISTINCT FROM 'timeout'`.

## Senior

### 1. Guarded `running -> succeeded`: zero rows and the remaining concurrency limit.

Question:

Write a guarded `running -> succeeded` transition. What does zero rows mean, and what concurrency
limitation remains?

中文解析:

`WHERE` 同时携带身份和当前状态：`WHERE job_id = $1 AND job_status = 'running'`，设置 `finished_at = now()` 与 `result_object_key = $2`（Object Storage 引用，不是字节），并用 `RETURNING` 作为证据。因为 `job_id` 是主键，结果只能是 1 行（转换发生）或 0 行（未发生）。**0 行不能推断 Job 不存在**——它可能处于其他状态，所以绝不能上报成功。剩余限制是并发：两个 worker 可能同时操作同一行；事后再 `SELECT` 诊断也可能读到已被改变的状态。要精确分类需要事务与行锁（Day33/Day34）。

Student's actual attempt (preserved):

> "where is the most important endpoint,the first need to limit job_id,and limit  job_status equal running.if the result return zero rows,it means all rows is not modify. i think the concurrency limitation is probobly two work concurrency modify the same row."

Interview Review: 守卫写法与 0 行解读都正确，并发直觉（两个 worker 改同一行）也对。需要收紧结论：0 行只证明**转换未发生**，不证明 Job 不存在。

Standard Answer:

I would guard the update with both the identity and the current state: `WHERE job_id = $1 AND job_status
= 'running'`, set `finished_at = now()` and the result reference, and use `RETURNING` as evidence. Since
`job_id` is the primary key, I get one row if the transition applied and zero rows if it did not. Zero
rows does not prove the Job is missing — it may exist in another state, so I would not report success.
The remaining limitation is concurrency: two workers can act on the same Job, and a follow-up `SELECT`
can be stale because the row may change between statements. Making that classification exact requires a
transaction and row locking, which is a later topic.

Follow-up Question:

A broad `UPDATE` just marked 842 running Jobs as failed. What is your first action, and why not wait?

## Common Weak vs Strong Answer (Day30)

```text
Weak:   "The update returned zero rows, so that Job doesn't exist."
Strong: "Zero rows means the guarded transition did not apply. The Job may exist in another state, so I
        don't report success; diagnosing the current state needs a separate query and, to be exact, a
        transaction."

Weak:   "We use parameterized SQL, so the endpoint is secure."
Strong: "Parameter binding closes the injection boundary because values are never parsed as SQL
        structure. Authorization, tenant ownership, business validation, and concurrency are still my
        responsibility, and identifiers need an allowlist."

Weak:   "RETURNING gives me the number of affected rows."
Strong: "RETURNING gives the actual rows the statement produced; the count comes from the driver's
        command result or the number of rows I received."

Weak:   "We rolled back the release, so the 842 wrongly failed Jobs are fixed."
Strong: "Code rollback only stops future bad writes. I contain first, preserve the RETURNING evidence,
        identify the affected set, reconcile each Job's real outcome against worker logs, provider
        status and result objects, then repair verified subsets with guarded statements."
```
