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
