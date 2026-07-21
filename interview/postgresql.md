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

---

# Day31 Relational Modeling and Data Integrity Questions

From the Day31 lesson: entities and cardinality, primary vs foreign vs business key, uniqueness scope,
referential actions, `CHECK` boundaries, normalization, tenant-aware composite foreign keys, integrity
vs authorization, and deploying a constraint onto committed duplicates.

Lesson: `docs/postgresql/day31-relational-modeling-and-data-integrity.md`

## Beginner

### 1. Primary key vs foreign key.

Question:

What is the difference between a primary key and a foreign key in a relational database?

中文解析:

主键唯一标识表中的每一行，值必须唯一且**不能为 NULL**——它回答"这一行是谁"。外键引用**另一张表（或同一张表）**的主键或唯一候选键，强制参照完整性：子行不能引用不存在的父行——它回答"这一行属于哪个父级"。注意外键不是"来自另一个 schema 的列"，与 schema 命名空间无关。

Student's actual attempt (preserved):

> "primary key means same value can't insert twice,foreign key means column comes from othrer schema"

Interview Review: 识别了主键的唯一性，但遗漏了"不能为 NULL"和"标识行"；外键的定义有误——它引用的是另一张表的主键/唯一键，与 schema 无关。英文：`othrer` → other。

Standard Answer:

A primary key uniquely identifies each row in a table. Its values must be unique and cannot be null. A
foreign key references a primary or unique key in another table and enforces referential integrity, so a
child row cannot reference a parent row that does not exist.

Follow-up Question:

If `job_id` is already a primary key, why is a separate uniqueness rule still needed?

## Intermediate

### 1. Why both `UNIQUE(tenant_id, idempotency_key)` and a primary key on `job_id`?

Question:

Why do we need both `UNIQUE(tenant_id, idempotency_key)` and a primary key on `job_id`?

中文解析:

`job_id` 主键唯一标识**数据库行**，但它阻止不了重复的**业务请求**——因为客户端重试时会生成一个**新的 job_id**，两行都是合法的唯一行。真正需要约束的是"同一租户内的同一次客户端请求"，所以用 `UNIQUE (tenant_id, idempotency_key)`。把 `tenant_id` 放进作用域，是为了让**不同租户可以复用同一个 idempotency key**。核心区分：行身份 vs 业务操作身份。

Student's actual attempt (preserved):

> "because UNIQUE (tenant_id, idempotency_key) means tenant_id bond on idempotency_key,the consist can't appear more than once in table.the truth is that a tenant can't request twice in same job_id.there are some problems,for example,different tenant_id also could bond idempotency_key."

Interview Review: 识别了组合作用域唯一性和跨租户可复用，方向正确。关键纠正：重试会产生**不同的 job_id**，这正是需要独立业务键约束的原因。

Standard Answer:

The primary key on `job_id` uniquely identifies one database row. It does not prevent duplicate business
requests because each retry can generate a new `job_id`. The unique constraint on
`(tenant_id, idempotency_key)` identifies a client request within one tenant and prevents that request
from creating multiple Jobs. Different tenants may reuse the same idempotency key because the uniqueness
scope includes `tenant_id`.

Follow-up Question:

You need to add that constraint to a table that already contains two duplicate Jobs. What do you do first?

### 2. Choosing a referential action for audit-bearing children.

Question:

`job_attempts` stores Provider request IDs, errors, and cost. Which `ON DELETE` action do you choose?

中文解析:

选 `ON DELETE RESTRICT`。`SET NULL` 在 `job_id NOT NULL` 上根本不可行；`CASCADE` 语法上可行，但它意味着一次误删父 Job 就会**连带抹掉审计与成本证据**——正是事故复盘最需要的数据。参照动作表达的是**生命周期与保留策略**，不是便利设置。`CASCADE` 适用于子行没有独立保留价值、且业务明确要整体删除聚合的场景；`SET NULL` 只适用于孤儿行仍有业务含义且外键列可空。

Standard Answer:

I would use `ON DELETE RESTRICT`. `SET NULL` is impossible because `job_id` is `NOT NULL`, and `CASCADE`
would let one accidental parent deletion erase the Provider, error, and cost evidence needed for audits
and incident reconstruction. The referential action encodes lifecycle and retention policy: `CASCADE` is
appropriate only when the child has no independent retention value, and `SET NULL` only when an orphaned
child is still meaningful.

## Senior

### 1. Tenant isolation with separate foreign keys.

Question:

Why are separate Job and Document foreign keys insufficient for tenant isolation, and how would you
enforce the rule in PostgreSQL?

中文解析:

两个独立外键只各自证明 Job 存在、Document 存在，**都不检查两者是否属于同一租户**——所以 Tenant-A 的 Job 可以合法地关联 Tenant-B 的 Document。做法：在中间表加 `tenant_id`，在父表上建租户感知的候选键 `UNIQUE (tenant_id, job_id)` 与 `UNIQUE (tenant_id, document_id)`，然后从中间表用**复合外键** `(tenant_id, job_id)`、`(tenant_id, document_id)` 引用它们——同一个 `tenant_id` 必须同时满足两个引用，跨租户关联会被 PostgreSQL 拒绝（`23503`）。但必须区分：这是**写入时的关系完整性**，不是**授权**。读取仍需带上从**已认证的服务端上下文**导出的租户谓词（`WHERE tenant_id = $1 AND ...`），RLS/角色是后续的纵深防御。

Student's actual attempt (preserved):

> "it must add some constraint about uniquely identifies (Tenant_id,job_id),(Tenant_id,document_id) on sperate table,we can create a inner table"

Interview Review: 技术方向正确。用词纠正：junction/association table（不是 "inner table"）、separate（拼写）、父表**复合候选键**、租户感知的**复合外键**。

Standard Answer:

Separate foreign keys only prove that the Job and Document exist. They do not prove that both rows belong
to the same tenant. I would add `tenant_id` to the junction table, define unique tenant-and-resource keys
on the parent tables, and use composite foreign keys from `(tenant_id, job_id)` and
`(tenant_id, document_id)`. PostgreSQL will then reject any cross-tenant relationship. This enforces
relational integrity, but request authorization still requires tenant-scoped queries or database
row-level security.

Follow-up Question:

Do those composite foreign keys stop a `SELECT` from returning another tenant's rows?

## Common Weak vs Strong Answer (Day31)

```text
Weak:   "The child table's job_id is the primary key, so each Job has its attempts."
Strong: "That would mean at most ONE Attempt per Job. The Attempt needs its own attempt_id primary key,
        a job_id foreign key, and UNIQUE (job_id, attempt_number) for the business rule."

Weak:   "job_id is unique, so a retried request can't create a duplicate Job."
Strong: "A retry generates a new job_id, so row identity can't help. The business key
        (tenant_id, idempotency_key) is what prevents duplicate requests."

Weak:   "We have composite foreign keys, so tenants are isolated."
Strong: "Those enforce relationship integrity at write time. A SELECT without a tenant predicate still
        returns other tenants' rows — authorization needs a server-derived tenant scope or RLS."

Weak:   "The duplicate Job was created later, so roll it back."
Strong: "ROLLBACK only applies before COMMIT. Both rows are committed, and the newer one may hold the
        Provider calls and the client-visible job_id. I reconcile the evidence, choose the canonical
        Job, repair verified subsets, then add the constraint."

Weak:   "The constraint tests passed, so the schema is correct."
Strong: "They prove the executed invariants in the executed schema. Atomicity, concurrency, migration
        safety, performance, and production correctness are all still unproven."
```

---

# Day32 SQL Joins, Aggregation, and Operational Queries Questions

From the Day32 lesson: result grain, `INNER` vs `LEFT JOIN`, join cardinality and row multiplication,
NULL-aware counting, `FILTER` vs `WHERE`, `WHERE` vs `HAVING`, `SUM`/`AVG` over incomplete data, CTE
pre-aggregation, stage-aware stuck detection, half-open windows, release provenance, and why an
operational query produces evidence rather than a verdict.

Lesson: `docs/postgresql/day32-sql-joins-aggregation-and-operational-queries.md`

Query pack: `projects/ai-backend-data-layer/sql/004_sql_joins_aggregation_and_operational_queries.sql`

## Beginner

### 1. `INNER JOIN` vs `LEFT JOIN` on an operations dashboard.

Question:

Your queue dashboard joins `jobs` to `job_attempts` with `INNER JOIN`, and queued Jobs are missing from
the output. Explain why, and what you would change.

中文解析:

`INNER JOIN` 只返回**两侧都匹配**的组合。刚创建、尚未被 Worker 取走的 Job 在 `job_attempts` 里还没有任何行，
所以整行被丢弃——而这恰恰是运维最需要看到的积压。改成 `LEFT JOIN` 后每个 Job 都保留一行，Attempt 列为 NULL。
这里的 NULL 是**有意义的运维证据**（"不存在 Attempt 行"），不是脏数据。判断标准是：**缺失本身是否是信息**。

Student's actual attempt (preserved):

> "因为使用INNER JOIN，所以查询的时候是两个表都存在job_id条件才成立，而刚创建但尚未被 Worker 处理，代表这个时候app.job_attempts还没有数据写入选择left join"

Assessment: correct, including the reason. To strengthen it, state the resulting grain explicitly.

Strong answer:

> "`INNER JOIN` returns only matching combinations, so a Job with zero Attempts disappears — which hides
> the backlog. I would use `LEFT JOIN`, giving a grain of one row per Job-Attempt combination, where a
> zero-Attempt Job produces exactly one row with NULL Attempt columns. That NULL means 'no Attempt row
> exists', which is the operational signal we are looking for."

### 2. What does `COUNT(*)` count after a `LEFT JOIN`?

Question:

After `LEFT JOIN app.job_attempts` and `GROUP BY j.job_id`, what do `COUNT(*)` and
`COUNT(a.attempt_id)` return for a Job with zero Attempts?

中文解析:

`COUNT(*)` 统计的是**结果行数**，包含外连接补 NULL 的那一行，所以是 `1`；`COUNT(a.attempt_id)` 只统计
**非 NULL** 的子表标识，所以是 `0`。要回答"这个 Job 到底有几次 Attempt"，永远数子表的键。

Strong answer:

> "`COUNT(*) = 1` and `COUNT(a.attempt_id) = 0`. `COUNT(*)` counts result rows, and the NULL-extended
> outer-join row is still a row. `COUNT(child_pk)` counts non-NULL child identities, which is what
> 'how many Attempts exist' actually means."

## Intermediate

### 1. Why can joining two child tables corrupt an aggregate?

Question:

A Job has 3 Attempts and 4 Events. You join both in one statement to report counts and total cost. How
many rows do you get, and what breaks?

中文解析:

join 返回的是**所有匹配组合**，不是逐步过滤：3 x 4 = 12 行。每个 Attempt 的 `cost_micros` 被重复 4 次，
`SUM` 直接放大 4 倍，`COUNT` 同样失真。结构性修复是**先各自聚合成每个 Job 一行的 CTE，再一对一 join**。
`COUNT(DISTINCT ...)` 只能修复计数，`SUM` 仍然是错的，而 `SUM(DISTINCT ...)` 本身就是错的——两次 Attempt
完全可能花费相同金额。

Student's actual attempts (preserved):

> "返回4行，因为先是查询出来三条job—attempt的结果集。再连接查询，有4过 job events，没查到的Attempts就用null代替"

> "返回0条，因为结果集job- attempt匹配到0条，再用这个结果集去匹配event结果还是0"

Assessment: both incorrect, and the shared root cause matters more than the numbers — the mental model
was a **sequential filter** rather than a combination product. Corrected in class to 12 rows, plus the
zero-Attempt case where 0 Attempts and 4 Events yields **4** rows, not 0, because the NULL-extended Job
row matches every Event.

Strong answer:

> "Twelve rows — a join returns every matching combination, and the database has no idea which Event
> belongs to which Attempt because that relationship was never modelled. `SUM(cost_micros)` is therefore
> multiplied by the Event count. I would pre-aggregate each child in its own CTE to one row per job_id,
> then `LEFT JOIN` those summaries, which are one-to-one and cannot multiply."

### 2. `FILTER` vs moving the condition into `WHERE`.

Question:

You need per-Job `total_attempts` and `failed_attempts`. Why not just add
`WHERE a.error_code IS NOT NULL`?

中文解析:

`WHERE` 过滤的是**进入聚合前的输入行**。把这个条件放进 `WHERE` 会删掉所有成功的 Attempt 行，也会删掉零
Attempt Job 的那一行占位行——等于把 `LEFT JOIN` 悄悄退化成 `INNER JOIN`。正确做法是把条件放进聚合内部：
`COUNT(a.attempt_id) FILTER (WHERE a.error_code IS NOT NULL)`，可移植写法是
`SUM(CASE WHEN a.error_code IS NOT NULL THEN 1 ELSE 0 END)`。

Student's actual attempt (preserved):

> "不知道"

Assessment: `FILTER` was unknown and taught directly. The durable rule: `WHERE` shapes the input set,
`FILTER` shapes one aggregate.

Strong answer:

> "`WHERE` removes input rows before grouping, so it would drop successful Attempts and the zero-Attempt
> placeholder row — collapsing the `LEFT JOIN` into an `INNER JOIN` and destroying the denominator of my
> failure rate. `FILTER` applies the condition to a single aggregate while leaving the row set intact."

### 3. `WHERE` vs `HAVING` for a retry threshold.

Question:

Return only Jobs that retried at least twice. Where does `COUNT(a.attempt_id) >= 2` go, and where does
`tenant_id = $1` go?

中文解析:

聚合结果在分组之后才存在，所以计数阈值必须放 `HAVING`。而租户、状态、原始时间等谓词应尽量放 `WHERE`，
让无关行**根本不进入聚合**——既更正确也更省。

Student's actual attempt (preserved):

> "HAVING"

Assessment: correct.

Strong answer:

> "`HAVING COUNT(a.attempt_id) >= 2`, because the aggregate does not exist until after grouping.
> `WHERE j.tenant_id = $1` stays in `WHERE` so other tenants' rows never enter the aggregation at all."

## Senior

### 1. A finance report sums `cost_micros` and some values are NULL.

Question:

Is the total correct? Would you wrap it in `COALESCE(SUM(cost_micros), 0)`?

中文解析:

聚合函数跳过 NULL，这在机制上没错，但 NULL 的含义是**未知**，不是零——Provider 调用完全可能真的花了钱只是
没上报。所以 `SUM` 得到的是**已记录成本**，`AVG` 的分母也只是**上报过的 Attempt**。诚实做法：列名写成
`recorded_total_cost_micros` / `recorded_average_cost_micros`，并在旁边发布完整度
（`COUNT(cost_micros)` 对比 `COUNT(attempt_id)`）。`COALESCE(..., 0)` 把"我们不知道"升级成"它没花钱"
这个自信断言，而这个断言会直接进入计费决策。

Student's actual attempts (preserved):

> "SUM(cost_micros)如果有null值就会跳过。AVG(cost_micros)也是同理，跳过null值再进行计算"

> (on COALESCE) "不可以"

Assessment: mechanically correct on NULL skipping, and correct to reject `COALESCE`. The addition made in
class was the engineering consequence — the number is a claim about your **records**, so it must be named
that way.

Strong answer:

> "It is the total of recorded costs, not incurred costs. NULL means unknown, not zero, and `AVG` divides
> only by the Attempts that reported. I would name the columns `recorded_*` and publish
> `cost_reported_attempts` beside `total_attempts` so the reader sees completeness. I would not use
> `COALESCE(..., 0)` — that converts ignorance into a confident claim that it cost nothing, on a page
> someone bills from."

### 2. Stuck-Job detection: which clock, and what does the row prove?

Question:

Find Jobs stuck in `running`. Do you use `jobs.started_at` or the current Attempt's `started_at`? Does a
long-running Attempt prove the provider call is dead?

中文解析:

`jobs.started_at` 衡量的是**含重试的整体耗时**（面向客户 SLA），当前 Attempt 的 `started_at` 衡量的是
**此刻真正挂住的那次执行**（面向诊断）。选"当前 Attempt"需要确定性规则：
`DISTINCT ON (job_id) ... ORDER BY job_id, attempt_number DESC, attempt_id DESC`——`attempt_id` 兜底
正是 Day30 的确定性排序规则。输出必须是**候选分类**而非结论：行只能证明**没有记录到完成**，Worker 可能还
活着、Provider 可能只是慢、也可能是完成写入本身失败了。

Student's actual attempts (preserved):

> "app.job_attempts的started_at"

> (on whether it proves the call is dead) "不能"

Assessment: both correct, including the harder epistemic point.

Strong answer:

> "The current Attempt's `started_at`, selected with `DISTINCT ON (job_id)` ordered by `attempt_number
> DESC, attempt_id DESC` so ties are deterministic. And no — the row proves only that no completion was
> recorded. I classify candidates as `running_without_attempt`,
> `running_with_finished_current_attempt`, `running_attempt_over_threshold`, or
> `running_within_threshold`, and only external verification distinguishes a slow provider from a dead
> one."

### 3. After a bad release is rolled back, is the data correct?

Question:

A bad worker release ran for 90 minutes and was rolled back. How do you scope the damage, and is the data
now correct?

中文解析:

回滚只停止**后续错误写入**，既不修复已提交的行，也无法撤销外部副作用（Provider 扣费、已发出的邮件、已发布的
outbox 事件）。确定影响范围要用**已记录的溯源**：`e.metadata ->> 'worker_release_id' = $2`。时间窗口只是
代理，两端都会误收误漏——时间相关性不是因果。溯源必须在事故**之前**就写入，查询只能读到被写下来的东西。
Day32 的产物是只读的：Attempt 证据、Artifact 是否存在、outbox 是否已发布，以及一个 `evidence_class` 分类
——**没有任何 UPDATE**。已发布的 outbox 行意味着下游已经消费了错误数据，只修数据库并不能让消费者恢复正确。

Student's actual attempts (preserved):

> "使用job_events的metadata去查询"

> "回滚只是把版本还原到之前的版本，并没有修复已经处理的数据"

Assessment: both correct, and the second is the sentence the whole lesson builds toward.

Strong answer:

> "No. Rollback stops future bad writes; it does not repair committed rows or undo external side effects
> like provider charges and published outbox events. I scope the damage with recorded provenance —
> `metadata ->> 'worker_release_id'` — rather than a time window, which over- and under-collects at both
> edges. Then I produce read-only evidence per Job: Attempt counts and failures, whether result artifacts
> exist, and whether outbox events were already published. Repair is a separate, deliberate, audited
> operation, and downstream consumers of published bad data are a third track again."

## Common Weak vs Strong Answer (Day32)

```text
Weak:   "I'll join jobs, attempts and events and count them."
Strong: "Two independent one-to-many children multiply: 3 attempts x 4 events = 12 rows, so SUM and
        COUNT are both wrong. I pre-aggregate each child in a CTE to one row per job_id, then join."

Weak:   "COUNT(*) tells me how many attempts each job has."
Strong: "COUNT(*) counts result rows including the NULL-extended outer-join row, so a zero-attempt job
        returns 1. COUNT(a.attempt_id) returns 0, which is the real answer."

Weak:   "SUM(cost_micros) is the total cost."
Strong: "It's the total of RECORDED cost. NULL is unknown, not zero, so I name it recorded_total and
        publish how many attempts actually reported."

Weak:   "This job has been running 30 minutes, so the provider call failed."
Strong: "It proves no completion was RECORDED. The worker may be alive, the provider slow, or the
        completion write may have failed. It's a candidate, not a verdict."

Weak:   "We rolled back, so we're fine."
Strong: "Rollback stops future bad writes only. Committed rows, provider charges and published outbox
        events all persist — and published events mean downstream already consumed bad data."
```
