# FastAPI Interview

## Purpose

Interview questions and model answers for FastAPI backend development.

## Sections

- Routing
- Dependency Injection
- Pydantic
- Authentication
- Database Integration
- Testing
- Production Deployment

---

# Day14 Backend Architecture Questions

These questions come from the Day14 Mini Project & Backend Architecture lesson. They focus on
layered design, dependency injection, and production concurrency in FastAPI.

## Routing and Layering

### 1. Why keep routers thin?

Question:

Why should a FastAPI router stay thin?

中文解析:

路由只负责校验请求和委派给 Service。把业务逻辑留在路由里会导致重复、难以测试，并把 HTTP 和业务耦合。

Standard Answer:

A router should validate the request model and delegate to a service. Business logic in the
router is hard to test and couples HTTP with business rules.

Follow-up Question:

What is the responsibility of `main.py`?

Production Discussion:

`main.py` only creates the app, includes routers, and configures dependencies.

### 2. Request model vs response model.

Question:

Why define both a request model and a response model?

中文解析:

请求模型负责校验和记录输入，响应模型精确控制返回内容，避免泄漏内部字段。

Standard Answer:

The request model validates and documents input; the response model controls exactly what is
returned and avoids leaking internal fields.

Follow-up Question:

How do these models support OpenAPI docs?

## Dependency Injection

### 3. Why use `Depends()`?

Question:

Why inject services with `Depends()` instead of creating them in the route?

中文解析:

Depends() 提供请求级依赖注入，让服务可测试、可替换，依赖关系显式可见。

Standard Answer:

`Depends()` provides request-scoped dependency injection, making services testable, swappable,
and their dependencies explicit.

Follow-up Question:

How would you inject a fake LLM client in a test?

Production Discussion:

Injecting dependencies lets you swap providers and mock infrastructure without touching the
workflow.

## Async and Production

### 4. Blocking work in async endpoints.

Question:

What happens if you call a blocking function inside an async endpoint?

中文解析:

阻塞调用会冻结事件循环，让该 worker 上所有并发请求停滞。应使用异步库或 asyncio.to_thread()。

Standard Answer:

A blocking call freezes the Event Loop and stalls every concurrent request on that worker. Use
an async library or `asyncio.to_thread()` for unavoidable blocking work.

Follow-up Question:

How does FastAPI handle a client disconnect?

### 5. Keeping a slow endpoint responsive.

Question:

The endpoint depends on a 30-second LLM call. How do you keep the API responsive?

中文解析:

接收任务、立即返回 task_id、在 worker 中处理、暴露任务状态，而不是一直占用连接。

Standard Answer:

Return a `task_id` immediately, process the work in a worker, and expose task status. The API
stays fast while the job runs in the background.

Follow-up Question:

What task states would you model?

Production Discussion:

Queue + worker + status avoids connection pile-up and timeouts.

### 6. Production concurrency control.

Question:

How do you protect downstream systems under load?

中文解析:

用信号量限制并发，对 429 用指数退避重试，尊重连接池大小，目标是稳定吞吐。

Standard Answer:

Bound concurrency with a semaphore, retry with exponential backoff on HTTP 429, respect
connection-pool sizes, and optimize for stable throughput.

Follow-up Question:

Why is maximum concurrency not the goal?

Production Discussion:

Unbounded concurrency triggers 429s, timeouts, and pool exhaustion, which is slower overall.

---

## Day43 AI Job API Contract and Request Lifecycle (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day43), the
[Day43 lesson](../docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md), and the
[Day43 API contract](../projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md).

### Q1 — Where in the `POST /jobs` flow do you return `202`, and is "attempt to persist" enough?

Model answer:

Return `202` only after the one PostgreSQL transaction commits Job + `(tenant_id, idempotency_key)` uniqueness +
the Outbox dispatch intent. "Attempted to persist" is insufficient — a crash before commit would promise a
durable Job that does not exist. `202` means a durable async commitment exists, not that the work finished.

Student's actual answer (preserved verbatim):

> "响应应该放在最后，先 validate upload，再generate job_id以及attempt to persist Job + Outbox"

Assessment: correct ordering (validate → identity → persist → respond); the refinement is that the response
boundary is the COMMIT boundary, not "attempt."

### Q2 — What does `202` mean, and is `201` a redirect?

Model answer:

`202 Accepted` = a durable async commitment received, no result yet. `201 Created` = a resource created
synchronously — not a redirect (redirects are `3xx`). A successful `GET` of a found Job returns `200` with its
business status (`queued`/`running`) in the body.

Student's actual answers (preserved verbatim):

> "202表示已收到创建承诺，但是还没有结果。201表示跳转"

> "5xx，202是成功但是跳转，4xx找不到资源"

Assessment: the `202` meaning is right; corrections — neither `201` nor `202` is a redirect, and `4xx` is the
whole client-contract class, not only not-found.

### Q3 — The route matched but the PostgreSQL lookup timed out. `404` or `5xx`?

Model answer:

`5xx`. `404` is a completed lookup that found no allowed resource; a dependency that cannot complete the lookup
is a `5xx`. Faking a `404`/`202` on a DB outage lies about the state of the world.

Student's actual answer (preserved verbatim):

> "应该返回5XX，匹配了路由证明method+path都没问题，进入handler之后在数据库查询超时，则说明不是没有找到这个job_id，而是数据库无法确认"

Assessment: correct — "I looked and found nothing" (`404`) vs "I could not look" (`5xx`).

### Q4 — A retry arrives with the same idempotency key after a lost response. What do you return?

Model answer:

Same tenant + same key + same input → atomically find-or-return the original Job (same `job_id`/status_url), no
second Job/Outbox, via the `(tenant_id, idempotency_key)` unique constraint + create-or-return (not
`SELECT`-then-`INSERT`). Same key + different input → `409 Conflict`.

Student's actual answer (preserved verbatim):

> "返回原job，因为租户与稳定幂等键已经绑定在数据是唯一值"

Assessment: correct for same input; the additions are the database-uniqueness authority and the
same-key-different-input `409`.

### Q5 — How do you read a Job's status, and can a tenant read another tenant's Job by id?

Model answer:

`GET /jobs/{job_id}` reads committed truth (`200` + business status). Filter by `WHERE tenant_id =
trusted_authenticated_tenant AND job_id = :path_job_id`; a cross-tenant request returns `404` (not `403`) so the
API is not an existence oracle. A UUID is not authorization.

Student's actual answers (preserved verbatim):

> "使用get，因为get是请求查询"

> "不能，因为会跨租户调取到其他租户的job"

Assessment: correct — GET reads state; a cross-tenant miss must look like a genuine miss.

### Q6 — Should FastAPI wait for the eight-minute Provider call, and is a Background Task a durable Worker?

Model answer:

No and no. The HTTP lifecycle is short and must not hold the connection for a long Provider call; durable work is
Relay → Worker claim → Provider → guarded completion. An in-process Background Task is not a durable Worker — a
deploy/crash can lose it — so it suits only short disposable work (durable execution is Day55).

Student's actual answers (preserved verbatim):

> "结束，因为防止http连接被长时间占用"

> "不能，因为会导致进程长时间被占用"

Assessment: correct — return the promise fast; long/durable work lives outside the request.

### Q7 — Duplicate dispatch arrives twice. What stops a duplicate Provider call, and does Artifact existence prove success?

Model answer:

The first gate is the guarded `queued -> running`: 1 row → the winner may create Attempt/Event and call the
Provider; 0 rows → stop. Lease/fencing protects a stale completion later. Artifact existence is not success —
only the committed database fact decides completion.

Student's actual answers (preserved verbatim):

> (act on both deliveries?) "不可以，因为会造成重复调用"

> "只能依靠持久化数据库事实"

Assessment: correct — the guarded claim is the first duplicate gate; durable facts, not stored bytes, decide
completion.

### Q8 — How do you cancel a Job — `DELETE`?

Model answer:

Use `POST /jobs/{job_id}/cancel`. The reason is semantic, not a claim about what `DELETE` must do: cancelling an
async Job records that cancellation was *requested* (terminal outcome pending), which `DELETE` — a "remove the
resource" verb, even as a tombstone/soft delete — does not express. Persist an audited cancellation intent;
`cancel requested != cancellation completed` (a Provider call may be in flight); a retry returns the current
representation without duplicating the cancellation event (terminal mechanics are Day54).

Student's actual answer (preserved verbatim):

> "POST /jobs/{job_id}/cancel，因为DELETE会在数据库中删除持久化事实，之后无法恢复job，也无法进行审计"

Assessment: correct — cancellation is a durable, auditable intent whose semantics ("requested, outcome pending") a resource `DELETE` does not express.

### Q9 (Senior) — A bad release returned `202` before Job + Outbox commit. Contain and recover.

Model answer:

Contain admissions/route traffic away from the faulty release; preserve logs/traces; roll back the faulty API
release (not "the database transaction"); identify affected requests by release version, tenant, idempotency key,
request/trace ID, returned Job ID, and commit evidence; do not fabricate missing Jobs or blindly replay Provider
work; use controlled/audited recovery; add a regression test for the pre-`COMMIT` response window. An idempotent
retry may correctly return `202` for the same durable Job — avoiding a second durable Job is the goal, not
avoiding a second `202`.

Assessment: roll back the code that lied, then reconcile committed facts.

### Final Chinese synthesis (preserved verbatim)

> POST creates a Job inside the tenant idempotency boundary and writes the Outbox intent, returns `202` and a
> query URL; retries recover the original Job; GET reads the persisted Job state; Relay scans `published_at IS
> NULL`; Worker claims and executes.

Validation: CONCEPTUAL / STATIC CONTRACT REVIEW only — FastAPI / PostgreSQL / Relay-Worker / Redis-Object-Storage-
Provider / integration / production runtime NOT RUN. Pydantic v2 (Day44), DI/lifespan/adapters (Day45),
SQLAlchemy/Alembic (Day46-48), durable cancellation (Day54), Celery (Day55) are future boundaries.
