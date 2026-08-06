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

---

## Day44 Pydantic v2 and Structured AI Input/Output Contracts (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day44), the
[Day44 lesson](../docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md), the
[Day44 contracts design](../projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md), and the
runnable [code](../projects/ai-backend-data-layer/api/day44_pydantic_contracts.py) /
[tests](../projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py).

### Q1 (Beginner) — What is the purpose of a Pydantic model at an API boundary?

Model answer:

To validate and serialize data at a system boundary — ensuring request, response, and provider data follow the
declared types and constraints before the application uses them. It does not replace authorization or database
constraints.

Student answer (verbatim):

> "the purpose is check client illegal enter"

Assessment: the student had the core (check client input); the strong answer adds serialization, the response/
provider boundaries, and the "not a substitute for authorization or DB constraints" limit.

### Q2 (Intermediate) — Difference between valid JSON, Pydantic-valid, authorized, and committed business state?

Model answer:

Valid JSON only parses. Pydantic-valid also follows declared types/constraints/structure. Authorized data has
passed identity + permission checks (e.g. the upload belongs to the authenticated tenant). Committed business
state is durable database truth from a successful transaction. Four separate boundaries.

Student answer (verbatim):

> "valid JSON is not equal Pydantic-valid data,Pydantic-valid data follow the declared types and constraints.committed business state is the durable database truth.authorized data is authentic by server authentic"

Assessment: JSON/Pydantic/committed are right; the correction is that authentication proves identity while
authorization checks permission and tenant/resource ownership (the student conflated them).

### Q3 (Senior) — A bad release used `model_construct()` for untrusted Provider output; 37 Jobs are marked succeeded. Contain, roll back, repair, prevent recurrence.

Model answer:

Disable the affected Provider-completion path and route traffic away from the faulty release; preserve evidence
(release version, job/attempt/request/trace IDs, validation failures, original result references, audit
history); roll back the application release and restore `model_validate()`/`model_validate_json()`; add a
negative test proving invalid output never reaches completion; classify the affected Jobs by release window,
attempt records, and output shape; repair only confirmed-invalid records through an idempotent, audited process
without deleting history or blindly replaying paid Provider calls; reconcile Job/Attempt/Event/Result Artifact.
Code rollback protects future executions; committed facts need a separate audited repair.

Student answer (verbatim):

> "contain influenced version provider completion path,preserve release_version\job_id\attemp_id\request_id\trace_id,and cheack failure,don't delete wrong result and audit history.recovery model_validate()/model_validate_json(),add test to check new version stop  completion callback.Identify affected set classify illegal construct result then repair these result.verify Job、Attempt、Event、Result Artifact make sure public illegal succeeded."

Assessment: strong end-to-end direction (contain, preserve, restore validation, regression test, classify,
repair, reconcile); the strong answer tightens the idempotent/audited repair and the no-blind-replay boundary.

### Q4 (Intermediate) — Can Pydantic detect that an upload belongs to the authenticated tenant?

Model answer:

No. Pydantic validates declared structure; ownership is an authorization query using the trusted tenant ID + the
upload-session ID against durable state. Idempotency uniqueness and the commit stay with the PostgreSQL
constraint + transaction.

Student answer (verbatim):

> "不能发现"

Assessment: correct — structural validity is not authorization.

### Q5 (Intermediate) — `model_validate` vs `model_construct` for untrusted input?

Model answer:

Use `model_validate()`/`model_validate_json()` for untrusted input; `model_construct()` bypasses validation,
validators, nested conversion, and `extra="forbid"`, so it must never touch untrusted client or Provider input.
`model_dump()` serializes an already-validated model.

Student answer (verbatim):

> "model_validate()，因为可以进行验证，model_construct会跳过验证环节"

Assessment: correct — construct skips validation and is a trusted-data/perf tool, not a boundary tool.

### Q6 (Intermediate) — Why must a negative Provider-output test assert more than a `ValidationError`?

Model answer:

Because a dangerous implementation could perform the completion side effect before validating; the test must
assert both a `ValidationError` and that the completion callback never ran (an empty completion list).

Student answer (verbatim):

> "最终结果检查completion_calls如果发现没有数据就说明确实拦截了，如果有数据就说明拦截失效了"

Assessment: correct — the empty completion list proves the guard blocked the fake result, not merely that an
exception occurred.

### Final Chinese mental model (preserved verbatim)

> "Pydantic能检查客户端输入，也可以验证公开响应和 Provider 输出，只是结构验证，不负责证明租户授权或数据库提交。客户端请求以及Provider 输出可以通过Pydantic经过验证，授权是可以确认job属于哪个租户，数据库事务在经过Pydantic验证后可以做原子事务提交。当出现事故时，回滚Pydantic版本不能保证数据库事实也回滚"

Validation: REAL Pydantic v2 tests executed (Pydantic 2.5.0, pytest -> 24 passed; in-memory completion callback,
not PostgreSQL). FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/integration/production NOT RUN.

---

## Day45 Dependency Injection, Lifespan, Configuration and AI Provider Adapters (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day45), the
[Day45 lesson](../docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md), the
[Day45 composition design](../projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md), and the
runnable [code](../projects/ai-backend-data-layer/api/day45_composition.py) /
[tests](../projects/ai-backend-data-layer/api/test_day45_composition.py).

### Q1 (Beginner) — What is dependency injection in FastAPI, and why create a shared Provider client in the lifespan instead of a route?

Model answer:

DI means a component receives its dependencies rather than constructing them, which makes code testable and
replaceable. A shared Provider client owns long-lived HTTP connection-pool resources, so create it once in the
application lifespan at startup and close it once at shutdown; building it inside a route causes connection
churn, leaks Secret handling into HTTP code, and gives no controlled shutdown. `Depends` then supplies the
already-created client.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer covers receive-not-construct, the pooled-resource lifetime, and
why a route is the wrong place.

### Q2 (Intermediate) — A Provider API key is missing in a new deployment. What should Worker startup do, and how do you roll out the fix safely?

Model answer:

Fail fast: `Settings` validation raises, the Worker stays not ready and claims no Jobs, and it logs a safe,
allowlisted config event (stable code + settings version, no Secret). Roll out by starting new Workers with the
corrected config, requiring readiness, and only then draining the old ones; if the new config is still invalid,
keep the old healthy Workers and roll back. Config rollback is not a database rollback.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer covers fail-fast, safe logging, verify-new-before-drain-old, and
the code-vs-DB rollback boundary.

### Q3 (Senior) — A new Provider Adapter release returns invalid JSON. Day44 validation blocks completion, but several Jobs already called the Provider. Contain, recover, prevent recurrence.

Model answer:

Contain: stop the affected release from claiming new Jobs and route to a known-good version with correct drain.
Preserve: release/settings version (never the Secret), provider/model, job/attempt/request/trace IDs, error
category, and secure references to the original output. Roll back application code/config and deploy a healthy
Worker first, without claiming any DB history rolled back. Classify by release/time/attempt/output —
validation-before-completion does not prove the external call never happened. Recover only through an
idempotent, guarded, audited process after checking correlation/idempotency evidence, reconciling
Job/Attempt/Event/Artifact. Never blindly requeue/replay paid calls, mark invalid JSON succeeded, delete audit,
or fabricate a result. Add negative regression tests and a staged rollout.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer is the full contain → preserve → roll back → classify → guarded
audited recovery → reconcile → regression/staged-rollout arc.

### Q4 (Intermediate) — Does `Depends()` create an app-wide or cross-process singleton?

Model answer:

No. `Depends()` supplies an already-created dependency, and its default cache is request-local (within one
request's dependency graph), not shared across requests or processes. The shared app-scoped resource is created
by the lifespan; `get_provider` returns that lifespan-created instance. Ownership is per-process, so 8 Worker
processes hold 8 independent Provider clients.

Student answer (verbatim):

> "每个请求/Job 轻量创建"

Assessment: correct that the service is created lightweight per request/Job; the addition is that `Depends`
supplies (not creates) the shared client and its cache is request-local, and the lifespan owns the app-scoped
resource.

### Q5 (Intermediate) — Is `SecretStr` a security guarantee, and where may the API key appear?

Model answer:

`SecretStr` reduces accidental printing/repr/serialization exposure only; it is not memory encryption and does
not replace permissions, rotation, or secure logging. The key comes from validated `Settings` and is read only
at the adapter construction boundary; it never appears in Router code, Job payloads, public errors, routine
logs, or prompt/output traces. Safe logging is allowlisted: `safe_log_fields()` emits only non-sensitive labels
(`provider_name`, model, timeout, `settings_version`) and never the `provider_base_url`, which can carry
userinfo, an internal host/port, or a private endpoint path.

Student answer (verbatim):

> "Secret类型，不是明文的"

Assessment: partially right; the correction is that `SecretStr` hides display but is not encryption/total secret
security, and the key must never travel in payloads or logs.

### Q6 (Intermediate) — During graceful Worker shutdown, in what order do you stop, drain, and close?

Model answer:

Stop claiming new Jobs first, wait/handle in-flight work under a bounded drain window, then close the Provider
client — never close it first. If a drain deadline hits while a Provider call is in progress, do not blindly
requeue it: the external result state may be unknown, the call may have cost money or may return later, so
recovery uses correlation, idempotency, and audit (Day34 lease/fencing, Day40 at-least-once, Day55 recovery).

Student answer (verbatim):

> "先停止 claim 新 Job、等待/处理 in-flight Job，再关闭 client，因为provider的调用并没有停止，之后会返回错误的artifact，以及其他副作用"

Assessment: the ordering is correct; the one refinement is that the interrupted external result is *unknown*,
not necessarily a wrong artifact — hence a guarded, audited recovery rather than a blind requeue.

Validation: REAL local FastAPI composition tests executed with a FAKE no-network Provider (Python 3.10.12,
fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 -> 20 passed; completion target is an in-memory
list, not PostgreSQL). Real Provider SDK/network, PostgreSQL/SQLAlchemy, Celery/Redis, Secret rotation/drain,
and production NOT RUN.

---

## Day46 SQLAlchemy 2.0 Mapping for the Day42 Data Model (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day46), the
[Day46 lesson](../docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md), the
[Day46 mapping design](../projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md), and the
runnable [code](../projects/ai-backend-data-layer/api/day46_orm_mapping.py) /
[static tests](../projects/ai-backend-data-layer/api/test_day46_orm_mapping.py).

### Q1 (Beginner) — What does it mean to map an existing schema with an ORM, and is the ORM the schema authority?

Model answer:

Mapping means writing ORM models that faithfully represent an existing schema — its tables, columns, types,
defaults, and constraints — so code can use typed objects. In a system that already has a schema, the database
remains the authority; the ORM is a representation, not a redefinition, and deliberate changes go through a
migration tool (Alembic), not by editing the models.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer covers faithful representation, the database staying
authoritative, and migrations for change.

### Q2 (Intermediate) — Why keep `TEXT + CHECK` for status instead of a native enum, and why doesn't a nullable column enforce a conditional rule?

Model answer:

`TEXT + CHECK` is the existing database fact; a native enum changes the on-disk representation and is a migration
(Day48), not a mapping. A nullable column only allows NULL; it does not enforce "succeeded implies a finish
time." That rule is a CHECK enforced by PostgreSQL on every write path, and a negative test for it expects a
rejected write (CHECK violation / `IntegrityError`), not an empty result.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer separates mapping from migration and nullability from the CHECK.

### Q3 (Senior) — A release omitted the `app` schema and wrote accepted Jobs to `public.jobs`. How do you recover, and what evidence matters most?

Model answer:

Roll back the bad mapping/release to protect future writes, remembering that a code rollback does not undo the
committed rows. Preserve and classify correlation evidence — release version, job/tenant/request/trace IDs — and
the single most important signal is whether the client was already responded to, because it constrains what a
safe reconciliation may do. Then reconcile the mis-placed rows into the durable `app`-schema truth through an
idempotent, audited process — never blindly ignoring, copying, or deleting them.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer is the full contain → preserve/classify → reconcile arc with the
client-response signal and the code-vs-data rollback boundary.

### Q4 (Intermediate) — What makes a JobAttempt unique, and may Job B reuse `attempt_number = 1`?

Model answer:

`attempt_id` is globally primary-key unique, but the business uniqueness is `UNIQUE(job_id, attempt_number)` —
the retry ordinal is unique within one Job, not tenant-scoped and not global. So Job B may have its own Attempt
1. A second candidate key, `UNIQUE(job_id, attempt_id)`, exists so JobEvent can prove same-Job provenance.

Student answer (verbatim):

> (initial, incorrect) "uniquee(tenant_id,attemp_id)"; (corrected) "应该运行，因为属于不同job"

Assessment: the scope was first put on the tenant; corrected to Job-scoped, and the different-Job retry
reasoning is right.

### Q5 (Intermediate) — How do you guarantee a non-NULL Attempt belongs to the same Job, and what does a NULL `attempt_id` mean?

Model answer:

A composite foreign key `(job_id, attempt_id) -> job_attempts(job_id, attempt_id)` proves same-Job provenance; a
single Attempt FK would permit a valid Job plus an unrelated valid Attempt. With MATCH SIMPLE, a NULL
`attempt_id` leaves the composite reference unenforced — the intended Job-level Event. The composite FK does not
limit an Attempt to one Event.

Student answer (verbatim):

> (initial) "因为只依靠单列只能出现attempt_id一次"; (correct) "job_id 是job A，attempt_id是null，这代表Job-level event"

Assessment: the mechanism was first explained by single-column reasoning; corrected to the composite FK, with a
correct Job-level-event description.

### Q6 (Intermediate) — Does `create_all()` success prove the mapping matches the existing schema?

Model answer:

No. `create_all()` can build a fresh schema that differs from the live one, so success is not compatibility
evidence. Static metadata tests prove the declared mapping structure; real behavior requires an isolated
PostgreSQL runtime test that first applies the independent Day42 raw SQL, then asserts actual rejections (a
duplicate `(tenant_id, idempotency_key)`, a succeeded Job without `finished_at`) — a rejected write, not an
empty result. Neither is Day47 integration evidence.

Student answer (verbatim):

> "不能，还需要进行验证" — and: "属于静态验证，能证明ORM classes的语法没有错误，不能证明实际orm映射的PostgreSQL事实"

Assessment: correct — creation success is not compatibility; static structure vs real database behavior are
distinct evidence levels.

Validation: REAL static metadata-contract tests executed (Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3 -> 20
passed; declared structure only). PostgreSQL runtime NOT RUN (no server; `create_all()` not used and not
compatibility evidence). Sessions/transactions = Day47; Alembic = Day48; integration/production NOT RUN.

---

## Day47 Async Sessions, Transactions, Repository and Unit of Work (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day47), the
[Day47 lesson](../docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md), the
[Day47 design](../projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md), and the
runnable [code](../projects/ai-backend-data-layer/api/day47_async_uow.py) /
[fake-session tests](../projects/ai-backend-data-layer/api/test_day47_async_uow.py).

### Q1 (Beginner) — What is a Unit of Work, and why not share one AsyncSession across concurrent Jobs?

Model answer:

A Unit of Work groups database operations into one transaction with a single commit or rollback and owns exactly
one Session for its lifetime. You cannot share an AsyncSession across concurrent Jobs because it holds an
identity map, pending changes, and transaction state, so Jobs would pollute each other. The Engine and session
factory are process-scoped and shared; each request or Job gets a fresh UoW with its own Session.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer covers the UoW's single-transaction ownership and per-unit-of-work
Session vs process-scoped Engine/factory.

### Q2 (Intermediate) — Explain flush vs commit, and why a guarded UPDATE ... RETURNING avoids the SELECT-then-UPDATE race.

Model answer:

Flush sends pending SQL to the database inside the current transaction (so a server-generated id is available for
a dependent write) but it is not durable and other Sessions cannot see it; commit makes the work durable and
visible. A guarded claim is a single `UPDATE ... WHERE job_status='queued' RETURNING`, so exactly one Worker's
statement changes the row and gets a row back; SELECT-then-UPDATE reads then writes, letting two Workers both
read 'queued' and proceed. Zero rows returned is a normal stale/no-op, not an error.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer separates flush from commit and explains the atomic single-winner
claim.

### Q3 (Senior) — UoW 1 committed start facts, the Provider produced an Artifact, but UoW 2 crashed before commit. Recover, and say what evidence matters.

Model answer:

PostgreSQL retains only UoW 1's committed facts — running, Attempt 1 with its correlation/idempotency key, and the
job_started Event. The external Artifact may exist, but its DB reference, the succeeded state, and the completion
Event do not, because code rollback is not durable-data or external-side-effect rollback. On restart I open a new
UoW, inspect the durable Job/Attempt/Event truth, and verify the Provider/Artifact by correlation key. If
confirmed, I run a new guarded completion transaction; if it cannot be verified, I preserve an unknown/recovery
state rather than fabricating success or blindly re-calling the Provider.

Student answer (verbatim):

> "不知道"

Assessment: an honest "不知道"; the taught answer is the full evidence-based recovery arc with the code-vs-data
rollback boundary and the unknown-outcome state.

### Q4 (Intermediate) — Who owns commit for Job -> Attempt -> Event, and what happens if the third insert fails?

Model answer:

The Unit of Work owns commit/rollback/close; repositories only express operations on the UoW-injected Session and
never commit. The three writes are one atomic transaction, so if the Event insert fails the UoW rolls back all
uncommitted work — a repository committing after a substep would persist a partial fact set.

Student answer (verbatim):

> "这是一个原子事务，既然第三个失败了应该是回滚整个事务，我觉得应该是Unit of Work外层统一决定" — and: "由 Unit of Work 把同一个 Session 注入给它"

Assessment: correct — atomicity is the UoW's one transaction; repositories share the injected Session but do not
decide commit.

### Q5 (Intermediate) — Why must a long Provider call stay outside the DB transaction, and when do you persist recovery identity?

Model answer:

A minutes-long, paid Provider call held inside a transaction exhausts the connection pool and still cannot be
rolled back by PostgreSQL — the database cannot undo external execution, charges, or side effects. So it runs
outside any transaction, between two short guarded UoWs. Before the call, commit an application-generated
correlation/idempotency key with the Attempt; the Provider's own request ID is persisted later and cannot be the
only recovery identity, because a crash can happen after the call begins but before the response is stored.

Student answer (verbatim):

> "不能，因为数据库事务无法控制外部调用" — and (recovery id, corrected): "获得 Provider 响应后" -> commit an app key BEFORE the call

Assessment: correct on the boundary; the correction is to commit the app-generated correlation key before the
call rather than relying only on the Provider-returned id.

### Q6 (Intermediate) — Does a mocked rollback() (or a SQLite run) prove PostgreSQL rollback behavior?

Model answer:

No. A mock asserting rollback() proves only code-path intent. A PostgreSQL runtime test must use a new Session
after the failure and prove committed truth — the Job remains queued and no Attempt/Event remains. SQLite is not
valid evidence for this system because the contract uses the app schema, PostgreSQL types/defaults/constraints,
and PostgreSQL transaction/concurrency behavior.

Student answer (verbatim):

> "不能" (for both SQLite and mock rollback as DB proof)

Assessment: correct — evidence must match the claim; only a fresh PostgreSQL Session read proves the rollback.

Validation: REAL fake-session control-flow tests executed (Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4,
pytest 7.4.3 -> 29 passed). PostgreSQL runtime NOT RUN (no server/driver; SQLite is not PostgreSQL evidence).
FastAPI/Worker integration, real Provider, Object Storage, production NOT RUN. Alembic = Day48; upload = Day49;
acceptance/Outbox = Day50.

---

## Day48 Alembic and Safe AI Backend Schema Evolution (Phase 4)

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day48), the
[Day48 lesson](../docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md), the
[Day48 design/runbook](../projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md), the
runnable [alembic package](../projects/ai-backend-data-layer/api/day48_alembic) / [backfill](../projects/ai-backend-data-layer/api/day48_lease_backfill.py), and the
[static tests](../projects/ai-backend-data-layer/api/test_day48_alembic.py).

> The student requested a direct final synthesis ("你帮我回答吧"); these are Tech-Lead-taught model answers, and
> the student explicitly answered "不知道" on `stamp`, new-vs-existing databases, and the full failure drill.

### Q1 (Beginner) — What is Alembic, and why is `alembic upgrade head` succeeding not the same as a safe migration?

Model answer:

Alembic records schema changes as a versioned graph of revisions (each with a `down_revision` predecessor).
`alembic upgrade head` succeeding only means the DDL executed on one database; it does not prove existing rows
are compatible, that old and new code can coexist, or that external side effects are safe. Safe migration is a
phased, evidence-gated process (Expand -> Backfill -> Validate -> Switch -> Contract), not a single command.

Student note: the student correctly saw an all-at-once change is unsafe — "不会，旧的worker与新增的列不兼容" — and
refused to fabricate historical Lease data — "不会，历史job不能伪造，追溯困难".

### Q2 (Intermediate) — Explain `NOT VALID` versus `VALIDATE`, and why they are separate steps on a populated table.

Model answer:

`CHECK ... NOT VALID` immediately enforces the new rule on every future INSERT/UPDATE while temporarily
tolerating pre-existing violating rows and avoiding a big blocking full-table scan. After the legacy rows are
backfilled/reconciled, `VALIDATE CONSTRAINT` (a separate revision) proves the historical rows also comply. They
are separate because future protection and historical proof are gated by different work; a failing `VALIDATE`
means the backfill/reconciliation isn't done (an exception queue is not resolution).

Student note: initially proposed `UPDATE ... RETURNING` (the Day47 runtime guard) — corrected to `CHECK ... NOT
VALID`; correctly described `VALIDATE` as "证明并纳入历史数据也符合已经上线的规则".

### Q3 (Senior) — Expand deployed, real Lease tokens exist, a faulty token guard, an old Worker may write, unknown Provider outcomes. How do you recover?

Model answer:

Stop old claims and the faulty paths and prevent any bypass writer, while preserving the real Lease data — no
destructive downgrade, because real data and Provider side effects exist. Drain/isolate old Workers; in a new UoW
load durable Job/Attempt/Event/correlation evidence and verify the Provider/Artifact; run a new guarded
completion only when confirmed, otherwise preserve an unknown/recovery state. Then forward-fix the guard,
reconcile, complete the backfill, `VALIDATE`, observe, and only then Contract. The Outbox row is dispatch intent,
not proof the Provider ran.

Student note: on the drill the student said "不知道" (direct teaching given); chose forward-fix elsewhere — "保留已
写入的 durable state 做 forward-fix，防止二次provider调用".

### Q4 (Intermediate) — Which Jobs get a backfilled Lease, and where does Backfill run?

Model answer:

Only running Jobs with trusted, provable ownership evidence are backfilled (their Lease triple is set on
`app.jobs`); queued and terminal Jobs get none, and unknown-running Jobs are routed into an **independent**
reconciliation queue table `app.job_lease_reconciliation` (`INSERT ... ON CONFLICT (job_id) DO NOTHING`, never
fabricated). Routing must NOT be a marker column on `app.jobs`: after the strict `jobs_running_requires_lease`
constraint, any UPDATE that left the row running with a NULL Lease would be rejected — so triage lives off the
business row and stays legal. The routed Job still counts as unresolved (routing didn't change `app.jobs`). Backfill
runs as a restartable operator script — short transactions, `FOR UPDATE SKIP LOCKED` batches (excluding queued Jobs
via `NOT EXISTS`), idempotent predicates, the database state as checkpoint — not as a long loop in an Alembic
`upgrade()`, and it calls no Provider.

Student note: classified "C backfill D reconciliation"; restart predicate "依赖仍是 running 且 Lease 字段仍为空、且
可信来源仍存在的行".

### Q5 (Intermediate) — Is deploying the new binary a completed Switch? And after real data, do you downgrade to fix a problem?

Model answer:

No — Switch requires that every Writer (Workers, recovery, admin scripts, completion/failure paths) uses the
token protocol and the old write path can no longer write; a new binary alone is not enough. And after real Lease
data or Provider side effects exist, you forward-fix and reconcile rather than destructively downgrade — a
downgrade loses data/history and can double-execute a paid Provider call. Contract is destructive and last, after
evidence and an observation period.

Student note: "不能，还缺少旧的work限制" (Switch) and "保留已写入的 durable state 做 forward-fix" (recovery).

### Q6 (Intermediate) — Does `alembic stamp` or an offline `--sql` render prove the migration is safe on PostgreSQL?

Model answer:

No. `alembic stamp` writes `alembic_version` and performs no DDL — it is only safe after the database is
independently proven to match the baseline. Offline `--sql` rendering and static graph/source checks prove the
migration text/structure, not database behavior, and SQLite/fake sessions are not PostgreSQL evidence. A real
`NOT VALID`/`VALIDATE` test needs PostgreSQL: create a legacy violating row, apply Expand + the separate constraint revision, prove the old row
survives, prove a new illegal write is rejected, and prove `VALIDATE` fails until the row is repaired.

Student note: "不能，因为还需要看实际运行"; on `stamp`/new-vs-existing DBs the student said "不知道".

Validation: REAL static/offline evidence executed (Alembic revision-graph + migration-source inspection and
fake-session backfill control flow -> 44 passed; Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3)
plus an offline `alembic upgrade --sql` DDL render. PostgreSQL runtime NOT RUN (SQLite/fake/`upgrade`-success are
not PostgreSQL proof); FastAPI/Worker integration, real Provider, Object Storage, and production migration NOT RUN.

---

## Day49 — Upload Sessions, Object Storage and Artifact Verification

Key vocabulary: presigned URL, bearer credential, bucket, object key, immutable version, ETag vs full-object
checksum, Upload Session, Document, ResultArtifact, idempotent finalization, guarded transition, fail-closed,
multipart upload, abort incomplete multipart, reconciliation, composite foreign key, tenant provenance.

### Q1 (Beginner) — What is a presigned URL, and can you trust the upload once it returns success?

Weak answer: "The client uploaded the file and storage returned 200, so the file is ready to use."

Strong answer: "A presigned URL grants temporary, limited permission to upload an object to a server-defined
storage location without exposing long-lived credentials. Before creating a Document, the backend must verify that
the stored object has the expected key, version, size, and checksum, and that it passes the required security
checks. An upload response alone does not prove the object is safe or suitable for business use."

### Q2 (Intermediate) — How do you finalize an upload safely and idempotently?

Strong answer: "I inspect and verify the immutable object outside the database transaction, comparing trusted
observed evidence against an expectation frozen before upload — I never rewrite the expectation and never treat an
ETag as a SHA-256. Then I open a short transaction, lock and re-read the Upload Session, create exactly one
Document, and mark the session verified in the same commit. A retry that finds the session already verified returns
the existing Document; a unique constraint on the upload session ID plus a guarded transition prevents duplicates.
If the database commit fails, I re-verify the same deterministic object instead of re-uploading it."

Follow-up: "Why not a client idempotency key here?" — "That is Day50's Job-acceptance concern; Day49's stable
identity is the upload_session_id plus the guarded transition and the unique constraint."

### Q3 (Intermediate) — Completion and cleanup race on the same session. How do you keep them safe?

Strong answer: "I serialize them on the database state with `SELECT ... FOR UPDATE` or a guarded UPDATE, and I never
hold a database lock across slow Object Storage I/O. If completion commits verified plus a Document first, cleanup's
eligible-state predicate affects zero rows and must not delete the object. If cleanup commits expired first,
completion's final guarded check fails and creates no Document. Cleanup commits the durable decision first, then
deletes the exact unverified object/version outside the transaction; a failed delete leaves a recoverable orphan,
not a dangling verified fact."

Follow-up: "URL expires 12:00, 2-minute skew, 1-minute buffer — earliest delete?" — "12:03: credential expiry plus
clock skew plus safety buffer."

### Q4 (Senior) — Recover an unknown multipart completion while the malware scanner is down.

Weak answer: "The Complete call timed out, so I restart the upload and skip the scan to keep moving."

Strong answer: "I first inspect the deterministic object reference to determine whether the multipart completion
actually succeeded; I do not restart the upload just because the response timed out. If the final object exists, I
verify its version, size, and checksum and preserve it for scanning. Because the scanner is unavailable, I fail
closed: the session stays in a verification state, no Document is created, and scanning is retried with bounded
backoff. The cleanup worker uses a guarded transition and must not delete an object that is being verified or has
already produced a Document. After the scanner succeeds, I finalize in a short transaction with a unique constraint
and a guarded transition. Unknown outcomes are reconciled from evidence instead of blindly retrying external side
effects — and I never re-call the paid Provider on recovery."

### Q5 (Senior) — Output ordering: mark the Job succeeded first, or write the result object first?

Strong answer: "Write and verify the output object first, then in a short unit of work insert the ResultArtifact
and JobEvent and guardedly mark the Job succeeded. Marking succeeded first can publish a false fact when the result
is absent. External-first can leave a recoverable orphan on a DB failure — recovered deterministically by key,
version, checksum, and Attempt correlation — which is strictly safer than a false success. On a crash after the
verified upload but before completion, I inspect the object and do an idempotent guarded completion without calling
the Provider again; if evidence is missing or inconsistent, I preserve the unknown/recovery state."

Production scenario / trade-off prompt: "UNIQUE vs composite FK for tenant provenance?" — "UNIQUE(upload_session_id)
guarantees at most one Document per session; same-tenant provenance needs the composite FK (tenant_id,
upload_session_id). The composite FK is relationship integrity, not authorization — that is Day52."

Validation: FAKE in-memory Object Storage adapter tests — application CONTROL FLOW only (Python 3.10.12,
pytest 7.4.3 -> 44 passed; hardened after Codex review rounds 1-2 — verification lease/fencing, exact-version binding before scan, and credential!=session timing). NOT real presigned/checksum/multipart/versioning semantics, NOT PostgreSQL runtime,
NOT a real Object Storage integration, NOT production. Day50 Outbox, Day51 JWT, Day52 authorization, Day55 Celery,
and a real Provider are not implemented.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day49), the
[Day49 lesson](../docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md), the
[Day49 design/runbook](../projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md),
the [model](../projects/ai-backend-data-layer/api/day49_upload_verification.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day49_upload_verification.py).

---

## Day50 — Idempotent AI Job API and Transactional Outbox Integration

Key vocabulary: idempotency key, request fingerprint, `UNIQUE(tenant_id, idempotency_key)`, `INSERT ... ON
CONFLICT`, transactional outbox, dispatch intent, relay, at-least-once, `published_at` checkpoint, `FOR UPDATE SKIP
LOCKED`, lease, fencing token, guarded claim, quarantine, exactly-once (not claimed).

### Q1 (Beginner) — What is an idempotency key, and why is it useful for an async AI Job API?

Weak answer: "it avoids calling the provider twice." (API acceptance comes first, and it is not only about the
Provider.)

Strong answer: "An idempotency key identifies one logical client request. If the client retries after a timeout, the
API returns the original Job instead of creating a duplicate Job and dispatch intent. This helps prevent duplicate
downstream processing."

### Q2 (Intermediate) — How does the transactional outbox prevent a Job accepted-but-never-dispatched?

Weak answer: "use at-least-once." (That is Relay/transport delivery, not the atomicity mechanism.)

Strong answer: "The API creates the Job and its dispatch Outbox event in the same database transaction, so either
both commit or neither does. After commit, a Relay reads the durable Outbox event and publishes it. Delivery is at
least once, so duplicates are possible, but an accepted Job never silently loses its dispatch intent."

Follow-up: "Why not `SELECT` then `INSERT`?" — "Two concurrent first-time requests both see absence and create
duplicates; `UNIQUE(tenant_id, idempotency_key)` plus an atomic conflict path is the arbiter."

### Q3 (Intermediate) — Same idempotency key, changed request body. What happens?

Strong answer: "It is a 409 Conflict with no new durable facts. The key is the identity of a logical command; the
fingerprint is server evidence that the key was not reused for a different command. Same key + same fingerprint
returns the original Job; same key + changed behavior-changing fields conflicts."

### Q4 (Senior) — A Relay publishes successfully but crashes before recording `published_at`. Recover without losing the Job or calling the Provider twice.

Weak answer: "Don't re-send, to avoid duplicate work." (The publish result is unknown; not re-sending can silently
lose an accepted Job.)

Strong answer: "The Relay scans Outbox rows where `published_at` is null. If it crashed after publishing but before
the checkpoint, it publishes again, because the result is unknown and the Job must not be lost — duplicate messages
are acceptable. Both Workers attempt a guarded `queued` to `running` update, but only one returns a row, so only
that Worker calls the Provider. A lease and fencing token also stop a stale Relay from writing a later checkpoint."

### Q5 (Senior) — Dispatch keeps failing past the retry policy. Do you mark the Job failed?

Strong answer: "No. I retain the original intent and evidence in a visible quarantined state, alert, and
controlled-replay. Job failure is a guarded business-execution terminal state; a quarantined Outbox means an
accepted Job still needs operational recovery. I never delete the intent silently and never fail the Job for a
transport problem."

Production scenario / trade-off prompt: "Do you hold the DB lock while publishing?" — "No. Publishing inside a lock
expands the transaction over uncertain external I/O, blocks Relay progress, causes lock waits/timeouts, and cannot
create a cross-system transaction. I use a short `FOR UPDATE SKIP LOCKED` claim with a lease, publish outside the
lock, then a fenced checkpoint."

Validation: FAKE in-memory store + transport tests — application CONTROL FLOW only (Python 3.10.12, pytest 7.4.3 ->
29 passed). NOT real PostgreSQL UNIQUE/tx/isolation/`ON CONFLICT`/`SKIP LOCKED`, NOT a real broker/Celery
(ACK/redelivery/poison), NOT Worker/Provider runtime, NOT integration/production. No exactly-once is claimed. Day51
auth, Day52 authz/quota, Day53 real Provider, and Day55 real Celery are not implemented.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day50), the
[Day50 lesson](../docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md), the
[Day50 design/runbook](../projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md),
the [model](../projects/ai-backend-data-layer/api/day50_job_acceptance_outbox.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day50_job_acceptance_outbox.py).

---

## Day51 — Authentication, Password Security and JWT

Key vocabulary: password hash, Argon2id, salt, work factor, `needs_rehash`, generic auth failure, JWT (signed vs
JWE), claims (`sub`/`iss`/`aud`/`exp`/`nbf`/`jti`), `kid` allowlist, algorithm pinning, asymmetric signing, key
rotation, Access vs Refresh, per-device session, refresh-token hash, guarded rotation, `UPDATE ... RETURNING`, retry
grace, replay detection, token family, HttpOnly/Secure/SameSite, CSRF.

### Q1 (Beginner) — password hash vs JWT

Weak answer: "A password hash is a hash stored at registration; a JWT is a short-term token issued after login."
(True but incomplete.)

Strong answer: "A password hash is one-way verification evidence stored with a slow adaptive scheme (Argon2id); the
raw password is never stored. A JWT is a short-lived signed identity credential issued after login — it is readable,
so it holds only non-secret claims and is trusted only after a full verification (algorithm, key, signature, issuer,
audience, expiry, subject)."

### Q2 (Intermediate) — what may never go inside a signed JWT, and what does verification require?

Strong answer: "A normal signed JWT is readable, so it must not contain a password hash, Provider key, prompt,
Document content, secret, or client-asserted tenant authority. Verification is a full contract: pin the algorithm,
select a trusted key by an allowlisted `kid`, verify the signature plus expected issuer, audience, expiry and
not-before, and require `sub`. Only the verified `sub` -> user_id is trusted; tenant authority is Day52."

### Q3 (Intermediate) — how does the guarded refresh rotation pick a single winner?

Weak answer: "use update returning, 1 row has priority, 0 rows has not."

Strong answer: "Rotation is one guarded transaction: `UPDATE ... WHERE current_hash matches AND session active AND
not expired RETURNING`. Exactly one concurrent request updates and receives the row, so exactly one new refresh
token is issued; a zero-row result saw a stale/revoked/expired/used token and issues nothing. All rotation state
commits or rolls back together, so a failure after marking A used but before B persists rolls back and keeps A
valid."

### Q4 (Senior) — a used refresh token reappears after the grace window

Weak answer: "Reject the request and delete the token family." (Deletion destroys audit evidence.)

Strong answer: "It is a suspected replay. Reject the request and revoke the affected token family, but RETAIN the
family record and audit evidence rather than deleting it; clear any bounded recovery material, alert, and require the
device to reauthenticate. Detection covers ANY previously-used token in the family, not just the most recent one: the
store keeps a per-family used-token ledger (`token_family_id + token_hash`), so replaying the oldest token A after
A->B->C is still caught. Revocation isolates only that device family — a different device for the same user is
unaffected. A short bounded grace window earlier does genuinely recover the lost response: the client that retries the
immediately-previous token in-window gets back the SAME usable replacement token B exactly once (held as short-TTL
encrypted recovery material, never a new A->C branch); that grace accepts a small bounded replay risk, and once the
one recovery is consumed the honest fallback is reauthentication. That recovery material is also minimum-retention: it
lives only until the grace deadline, and a scheduled sweep destroys the ciphertext and grace hash once the window
expires EVEN IF the client never retries — the used-token ledger and audit record are kept, so a later replay is still
detected, never degraded to a plain invalid-token result. And every explicit revoke path — single logout, family
revoke, and logout-all / password-change (`revoke_all_user_sessions`) — destroys that recovery material immediately
through one shared helper, so a security event never waits for the sweep."

### Q5 (Senior) — key authority, rotation, and emergency compromise

Strong answer: "The Auth Service holds the private signing key; API and Worker verify with public keys only, so a
verifier cannot mint tokens. `kid` is an allowlist identifier, never a URL or file lookup. Planned K1->K2 publishes
K2, trusts K1 and K2, signs with K2, and retains K1 verification for K1's maximum token lifetime plus clock skew
before dropping K1. On a confirmed K1 compromise I reject K1 immediately, before normal expiry, for BOTH verification
and signing: a revoked key can never sign again, and if K1 was the current signing key the issuer fails closed (no
token is minted) until an operator promotes the already-prepared K2 as the current signer. Then only K2 signs, and
already-issued K1 tokens fail verification at once. I accept the forced reauthentication."

Production scenario / trade-off prompt: "Is HttpOnly enough for a cookie-based refresh endpoint?" — "No. HttpOnly
blocks JavaScript reads but not automatic cookie attachment, so it is not CSRF protection. For cookie-authenticated
state changes I combine SameSite with Origin validation and a CSRF token, and reject a cookie-only cross-site request
lacking valid Origin/CSRF evidence."

Validation: REAL Argon2id + REAL RS256 JWT with ephemeral in-process keys + an in-memory guarded-rotation store
(Python 3.10.12; argon2-cffi 23.1.0, PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3 -> 37 passed). Proves crypto
primitives + control flow only. NOT real PostgreSQL (UNIQUE/tx/isolation/`UPDATE ... RETURNING`), NOT FastAPI/browser
(cookies/SameSite/Origin/CSRF at the wire) or a JWKS endpoint, NOT integration/production. JWE is out of scope. Day52
authorization/quota, Day53 real Provider, and Day55 real Celery are not implemented. No plaintext passwords, refresh
tokens, JWTs, or operational signing keys are committed.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day51), the
[Day51 lesson](../docs/fastapi/day51-authentication-password-security-and-jwt.md), the
[Day51 design/runbook](../projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md),
the [model](../projects/ai-backend-data-layer/api/day51_authentication_jwt.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day51_authentication_jwt.py).

---

## Day52 — Authorization, Tenant Isolation, Quotas and API Security

Key vocabulary: authentication, authorization, subject/user ID, tenant, tenant membership, role, permission/action, AuthorizedTenantContext, least privilege, resource scope, ownership predicate, IDOR/BOLA, existence oracle, RLS, rate limit, quota, concurrency limit, token bucket, sliding window, Retry-After, fail-open/fail-closed, reservation, reconciliation, idempotency key, request fingerprint, guarded `UPDATE ... RETURNING`, audit evidence, rollback, forward repair.

### Q1 (Beginner) — authentication vs authorization

Actual answer: "Authentication acts like an access control gate, while authorization defines the scope of resource usage."

Strong answer: "Authentication verifies who is making the request, for example by validating a JWT and extracting the user ID. Authorization then checks whether that user has the required permission in the current tenant to access or modify a specific resource."

### Q2 (Intermediate) — a client sends a different tenant_id

Actual answer: "It should be rejected."

Strong answer: "The backend treats the client-supplied tenant ID only as a requested tenant selector, not as authority. After JWT verification, it checks active Membership and the required action in tenant-A before loading the Job. The Job query is also tenant-scoped, so the user cannot access a Job from another tenant."

### Q3 (Intermediate) — why is a JWT role claim not enough for authorization?

Strong answer: "A role baked into a JWT goes stale: if I remove a user's Membership or downgrade their role, the old token keeps asserting the old role until it expires. For anything sensitive I check current active Membership and role per protected request, or use a short cache with an explicit revocation path. The JWT gives me a trusted user_id; the tenant authority decision is server-side."

### Q4 (Intermediate) — cross-tenant read: 404 or 403?

Strong answer: "A public 404. A 403 that says 'forbidden for tenant X' confirms the resource exists — an existence oracle. A tenant-scoped miss and a truly missing resource must look identical. A missing *action* can be a generic 403 because it doesn't point at a specific resource. Audit logs record the real decision as metadata; the client just sees 404."

### Q5 (Senior) — rate limit vs quota, and a limiter outage on a paid path

Strong answer: "Rate limit controls request speed, quota controls accumulated token/cost spend, and concurrency controls in-flight pressure — three different systems. Rate limiting must use a shared atomic coordinator like Redis, because four instances with local counters each allowing 100 admit about 400. Quota is durable truth in PostgreSQL, not Redis. If the limiter is unavailable on a paid POST /jobs, I fail closed and return 503 — a dependency-unavailable error — not 429, because 429 should only mean a healthy limiter confirmed an exceeded limit."

### Q6 (Senior) — guarded token reservation under concurrency and unknown cost

Actual answer: "An update set is used to return the result: returning one row indicates that the credit limit has been obtained, while returning zero rows indicates it has not. A rollback is performed if the operation fails. In the event of a timeout, it is necessary to save the record, secure evidence, and perform a manual fix."

Correction: one row means a guarded budget reservation atomically succeeded, not that a credit limit was "obtained"; on timeout, preserve evidence and first use reconciliation/correlation — manual escalation is the fallback.

Strong answer: "I would use a guarded database update that reserves tokens only when the tenant has enough available budget. Only one concurrent request can succeed; a zero-row result means the budget is no longer sufficient, so no Job or Outbox event is created. The reservation, Job, and Outbox intent commit in one transaction, and a failure rolls back all of them. If the Provider times out and actual usage is unknown, I keep the reservation and move the Job into a reconciliation state. I preserve correlation and audit evidence, then settle or release the reservation only after the Provider outcome is known. If the Provider actually spent more than I reserved, I never truncate the recorded usage or release the reservation as if settled — I record the exact observed usage and route it through an explicit overage reconciliation, because reserving only max_tokens can under-cover total billable cost. Reconciliation is idempotent: Provider callbacks are at-least-once, so a per-job lifecycle status makes a repeat of the same actual a no-op, a different actual after settlement a reconciliation conflict rather than a re-settle, and a post-overage plain callback a no-op — only an explicit controlled settlement changes the final budget fact, and even that never bypasses the hard quota: it charges the full observed usage only when the tenant has headroom or a trusted accounting/ops-approved credit covers the shortfall in the same atomic step, otherwise it stays in overage awaiting a top-up so available is never driven negative."

### Q7 (Senior) — idempotent recovery vs authorization and rate limiting

Strong answer: "I authorize first, then recover: same tenant + same Idempotency-Key + same command returns the original Job with no second reservation, Job, or Outbox. The fingerprint that proves 'same command' is computed server-side from the behavior-relevant fields (max_tokens, document_id, task_type) with a stable SHA-256 — the client supplies the key, never the fingerprint — so reusing the key with a changed max_tokens is a 409, not a wrongful replay. Recovery is not an authz bypass — if the user's Membership was removed, authorization fails before recovery runs. I rate-limit new commands, but I don't punish a lost-202 retry with the limiter; if I want abuse protection on reads I add a separate low recovery-read limit."

Production scenario / trade-off prompt: "A bad policy release gave members job.cancel. What do you do?" — "Contain it by rolling back the erroneous centralized job.cancel grant (or failing closed for member cancellation), not by stopping safe Job creation. That protects future traffic only. Then I classify the cancel intents already created by actor, tenant, Job, policy version, time, and whether Worker/Provider work happened, and I invalidate the bad pending intents with a guarded UPDATE ... WHERE intent_id AND policy_version AND state='pending' RETURNING. Zero rows means the fact changed — a legitimate cancel already executed — so I stop automatic repair and reconcile instead of overwriting it. I never delete intents; the ledger is audit evidence."

Validation: in-memory control-flow model, standard-library only (Python 3.10.12, pytest 7.4.3 -> 32 passed). Proves application control flow only. NOT real PostgreSQL (constraint/tx/isolation/UPDATE...RETURNING/RLS), NOT real Redis (distributed atomics/TTL/failover), NOT FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/routes), NOT Provider/Worker/integration/production. Day53 real Provider, Day54 streaming/cancellation, Day55 Workers not implemented. No real JWT, Provider key, password, prompt, or user data used.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day52), the
[Day52 lesson](../docs/fastapi/day52-authorization-tenant-isolation-quotas-and-api-security.md), the
[Day52 design/runbook](../projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md),
the [model](../projects/ai-backend-data-layer/api/day52_authorization_tenant_quota_security.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day52_authorization_tenant_quota_security.py).

---

## Day53 — OpenAI SDK, Provider Boundaries and Structured Output

Key vocabulary: Provider boundary, Adapter, application-owned interface, ProviderOutcome union, structured output, strict validation, `extra="forbid"`, server-owned schema registry, schema version binding, guarded completion, zero-row stop, execution contract, business success vs cost settlement, unknown usage, reconciliation-pending, refusal/incomplete/timeout classification, Provider 429 vs API 429, raw-data minimization, configuration rollback vs business-fact rollback.

### Q1 (Beginner) — what is a Provider boundary?

Strong answer: "A Provider boundary is an application-owned interface — for example `AIProvider.generate(request) -> ProviderOutcome` — that hides the vendor SDK. The Adapter behind it owns all SDK response and exception types and translates them into my own outcome types, so the rest of the system never depends on a specific Provider. It is not merely 'the data business logic needs from the response'."

### Q2 (Beginner) — where does the SDK boundary live?

Strong answer: "Inside the Adapter, not the Repository or database. The database must not depend on the SDK, but the boundary is even earlier: SDK request/response/exception types stop at OpenAICompatibleAdapter, which translates them into a provider-neutral outcome. Everything inward is vendor-neutral and testable with a fake transport."

### Q3 (Intermediate) — the Provider returns valid JSON missing a required field

Strong answer: "It parses but must fail validation. I validate the untrusted payload against the Job's bound server-owned schema with a strict model that forbids extra fields and requires the mandatory ones — a missing `citations` or a forbidden `debug_prompt` fails. On failure I never call the Completion Service: no success transition, Result Artifact, or Event, and I record a classified validation failure with field locations only, never the raw payload. Parsing support does not replace my validation gate."

### Q4 (Intermediate) — can a v2 output satisfy a Job contracted as v1?

Strong answer: "No. The Job binds a schema name and version at acceptance from a server-owned registry, and the persisted execution contract governs acceptance. A v2 payload validated against v1 fails — its extra field is forbidden — and there is no implicit truncation, downgrade, or guessed mapping. An unknown version is classified as schema-not-found, not silently downgraded. A real cross-version change needs an explicit, versioned, tested, audited migration."

### Q5 (Senior) — a Provider times out with unknown usage; can the Job succeed, and how is cost handled?

Strong answer: "Business execution success and cost settlement are separate axes. A timeout is a NON-terminal reconciliation outcome (not a definite FAILED). Because a Provider call is a paid side effect, eligibility is claimed BEFORE the call: an ATOMIC claim creates exactly one in-flight Attempt, so a terminal/pending Job or a concurrent Worker is pre-call blocked with zero transport calls and two Workers can't both issue a paid call. A matching late result is accepted by ingesting the already-issued outcome against its PERSISTED Attempt (validate attempt_id + correlation + provider request id, then guarded completion) — never by calling execute_job again; any late outcome on a terminal Job is a guarded no-op that never rewrites facts; and because callbacks are at-least-once, ingestion is concurrency-safe and idempotent — an atomic claim flips the Attempt to a processing state so two concurrent or duplicate deliveries dispatch at most once; a recorded provider request id must be matched exactly (a missing incoming id is rejected); and the dispatch is one UoW so a failure rolls back any partial write before reopening the Attempt. The important cost case is a valid result with unknown usage: the Job can succeed on the business axis while I keep the Day52 reservation and hold a cost reconciliation-pending state — I never record unknown usage as zero. Only the guarded `running -> succeeded` transition, owned by the Completion Service, writes the validated Result Artifact and commits a short UoW; if it updates zero rows I stop and reconcile rather than overwrite."

### Q6 (Senior) — error classification and a bad model rollout

Strong answer: "A refusal is a classified non-success, not an empty success. A 401/403 is a configuration/authentication failure, so I stop new calls with that Provider configuration and preserve safe evidence — it is not a user-input error. A 429 that happens after a durable 202 is a downstream Job/Attempt event, not a retroactive client 429; I keep a safe Retry-After and let Day56 own retry policy. For a rollout that switches to a model lacking research_summary.v1, new calls get a CONFIG-WIDE 400 capability failure that fails the Provider config closed (so no further new call uses it), but a legitimate old in-flight v1 result is a distinct call that still validates against its persisted contract and is accepted through guarded completion. A single non-config-scope 400 does not disable the whole config. And the outgoing call is always bound to the persisted execution contract — a caller cannot substitute the model, schema, or an enlarged token budget. The core rule is that configuration rollback governs future calls and is not a rollback of durable business facts."

Production scenario / trade-off prompt: "Should you persist the raw Provider response in the Result Artifact?" — "No, not by default. I persist the validated domain result, schema name/version, safe Provider metadata, a safe failure classification, correlation IDs, and the actual-usage/reconciliation state. Raw responses can carry prompts or secrets and bloat artifacts; any forensic raw-evidence store is a separate system with explicit minimization, redaction, access control, retention, and audit."

Validation: REAL Pydantic v2 strict validation + an in-memory Adapter->Validator->Completion model with an injected fake transport (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 48 passed). Proves the validation gate + application control flow only. NOT the real `openai` SDK/network/Provider, NOT PostgreSQL/Redis/Celery Worker, NOT FastAPI wire/integration/production. Day54 streaming/disconnect/cancellation, Day55 Celery, and Day56 retry/backoff are not implemented. No real api_key, prompt, Document content, or Provider response is used.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day53), the
[Day53 lesson](../docs/fastapi/day53-openai-sdk-provider-boundaries-and-structured-output.md), the
[Day53 design/runbook](../projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md),
the [model](../projects/ai-backend-data-layer/api/day53_openai_provider_structured_output.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day53_openai_provider_structured_output.py).

---

## Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation

Key vocabulary: HTTP connection lifecycle, Provider request lifecycle, durable Job lifecycle, SSE subscription, token streaming vs progress/event streaming, reconnection, Provider timeout, `PENDING_RECONCILIATION`, durable cancellation intent, cooperative cancellation, guarded terminal transition, zero-row stop, deadline/expiry, at-least-once observation, policy rollback vs business-fact rollback, evidence-based recovery.

### Q1 (Beginner) — what does an HTTP client disconnect mean for a durable Job?

Actual answer: "http client disconnect means subscribe finished, cancellation of a durable background Job is a durabel cancellation intent".

Strong answer: "An HTTP client disconnect just means the client subscription has ended — the durable background Job is unaffected and stays running. Cancelling a durable Job is different: it starts with a durable, auditable cancellation intent, then requires the Worker to cooperate and a guarded terminal transition to actually make it `cancelled`."

### Q2 (Beginner) — the two kinds of streaming and reconnection

Strong answer: "Provider token streaming is transient chunks for one Provider request; durable Job progress/event streaming is safe observable state for a persisted Job. A reconnecting browser reads/subscribes to the durable Job state and progress events, not a replay of Provider tokens — and I don't default-persist every token as an event because it inflates storage, can keep unvalidated or sensitive content, and breaks raw-data minimization."

### Q3 (Intermediate) — a Provider call times out; do you retry immediately?

Actual answer: "retry the provider call may waste provider".

Strong answer: "No — an immediate retry may waste Provider capacity, and more importantly a timeout leaves execution, result, and usage unknown, so an immediate retry can duplicate execution and cost. I move the Job to a reconciliation-pending state, keep the budget reservation, and reconcile from Provider correlation/usage evidence rather than fabricating a failure or a zero cost. The original 202 is not retroactively a 504; later state is observed through Job reads."

### Q4 (Intermediate) — a user cancels; can the Router write `cancelled`?

Strong answer: "No. The Router authorizes and persists a durable, auditable cancellation intent first — reason, timestamp, actor. A Worker observes the intent cooperatively at safe points: before the Provider call it doesn't call the Provider and takes a guarded terminal transition; mid-stream it best-effort aborts the stream and takes a guarded transition without claiming the remote model stopped or that cost is zero. I persist the intent first because it survives process loss, is auditable, and is re-observable at-least-once."

### Q5 (Senior) — design cancellation for a long-running, billable, streaming Job (incident runbook)

Strong answer: "First, an authorized cancel request persists a durable, auditable intent — it does not directly write `cancelled`. A Worker observes it cooperatively: pre-call it doesn't call the Provider and takes a guarded terminal transition; mid-stream it best-effort aborts the Provider stream, stops publishing tokens, records correlation evidence, and takes a guarded transition — without claiming the remote model stopped or that cost is zero, so unknown usage stays reconciliation-pending. Completion and cancellation both use guarded terminal writes, so exactly one wins and the loser sees zero rows and reconciles; a late valid result after a terminal cancel cannot flip the Job to succeeded. A crash after the intent is persisted is safe because a restarted Worker re-observes it and the guarded transition absorbs repeats. If a bad release turned disconnects into cancellations, my first step is to roll the policy back to stop new harm — that is not a business-fact rollback; I then build an affected set from release version and a bounded time window, keep the audit history, and reconcile each Job from Provider evidence instead of blindly flipping state or re-calling the Provider."

Production scenario / trade-off prompt: "Should you persist every Provider token so a reconnecting user can replay?" — "No, not by default. I persist low-frequency safe lifecycle milestones and the validated final Result Artifact; a reconnecting browser reads durable state and events. Default per-token persistence inflates writes/storage, can retain unvalidated/partial/sensitive content, and conflicts with raw-data minimization. A replayable partial-text product is a separate design with its own minimization, access, retention, idempotency, and cost decisions."

Validation: in-memory control-flow model — standard-library control flow; the late-result path REUSES Day53's pydantic-backed strict validation gate (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 27 passed). Proves application control flow only. NOT real FastAPI/SSE wire behavior, NOT the real OpenAI SDK/network/Provider token stream, NOT PostgreSQL/Redis/Celery, NOT integration/production. Day55 Celery and Day56 retry/backoff are not implemented. No real credentials, prompts, Document content, or raw Provider tokens are used.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day54), the
[Day54 lesson](../docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md), the
[Day54 design/runbook](../projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md),
the [model](../projects/ai-backend-data-layer/api/day54_streaming_disconnects_timeouts_cancellation.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day54_streaming_disconnects_timeouts_cancellation.py).

## Day55 — Celery, Worker Execution and Long-running AI Jobs

Key vocabulary: at-least-once delivery, redelivery, acknowledgement (ACK), visibility timeout, guarded claim, execution authority, durable Attempt, provider idempotency key, poison message, dead-letter, quarantine, envelope version, execution contract, reconciliation, graceful drain, revoke.

Useful expressions: "ACK means the delivery was handled, not that the Job succeeded." · "A guarded claim in PostgreSQL decides execution authority; the broker only delivers." · "An unknown outcome is reconciliation, not a failure and not a blind retry."

### Q1 (Beginner) — What does a Celery task SUCCESS mean?

Strong answer: "It means the delivery was reliably handled — an operational delivery/execution status. The business Job is only `succeeded` when PostgreSQL, the source of truth, records it through a guarded completion. I read the durable Job (`GET /jobs/{id}`), not the Celery result backend." (Student's own EN: "celery task being success means task response success that is a temporary state; durable job is a truth.")

### Q2 (Intermediate) — Two Workers get the same Job. Prevent a double Provider call.

Strong answer: "The first duplicate-call gate is an atomic PostgreSQL guarded claim: `UPDATE ... WHERE status IN ('queued','running') RETURNING`. One Worker gets one row and the authority to call the Provider; the other gets zero rows and stops before the call. A lease or fencing token is secondary — a lease is temporary ownership and fencing rejects stale writes but can't undo an external call. Redelivery keeps the same Attempt and the same provider idempotency key; only an explicit, durable, authorized A2 gets a new key." Weak answer: "Celery dedups retries for me, so redelivery is safe."

### Q3 (Intermediate) — Envelope poison vs execution-contract poison vs transient failure.

Strong answer: "`job.dispatch.v2` I can't parse is envelope compatibility — checked before I load the Job — so I dead-letter and ACK with zero Provider calls, Job untouched. An unsupported persisted execution contract is checked after I load the Job, so I durably quarantine it and ACK, zero calls. A transient transport failure is different: bounded retry with exponential backoff and jitter — that depth is Day56 — while I retain the Attempt and evidence and let it redeliver. Deterministic poison never uses an ordinary infinite requeue." (Student intermediate EN: "guarded completion.")

### Q4 (Senior) — Provider timeout / Worker OOM mid-call. Cost? Re-call?

Strong answer: "Neither cost nor execution is known. OOM means the OS or container killed the Worker with no chance to clean up, so exception handling alone is insufficient — that's why I persist the guarded claim, Attempt, correlation, and `provider_request_id` before the call and keep the long call outside any DB transaction. On an unknown outcome I retain the reservation, enter `PENDING_RECONCILIATION`, never fabricate zero usage, and never blind re-call. A redelivery of that Job reconciles from the existing Attempt evidence and calls the Provider zero times."

### Q5 (Senior) — Design cancellation + incident recovery for long-running Celery AI Jobs.

Strong answer: "Cancellation is a durable, auditable intent committed first — reason, actor, timestamp, version. The Celery revoke is best-effort delivery control after the commit, never the authority; it can fail or race. Workers check the intent at safe points: pre-call means zero Provider calls and a guarded terminal (user cancel -> CANCELLED, deadline -> EXPIRED); a final pre-completion check stops a late `succeeded`. Completion and cancellation both use guarded terminal writes, so exactly one wins and the loser sees zero rows. For an erroneous early-ACK release, I roll the configuration back first to stop future harm — that is not a business-fact rollback — then build an affected set from the release version, a bounded time window, and Worker/Attempt/Event evidence. I don't bulk-flip running Jobs; I reconcile each from evidence and only re-dispatch, under a guarded audited action, the Jobs with no Provider-execution evidence." (Student senior EN, verbatim: "rollback configuration, contain worker request new job admission. classify job running status, like provider calling or not yet or happen cost. use attempt event usage provider request id artifact idempotency key guarded repaire.")

Production scenario / trade-off prompt: "Publish the Celery task before or after the Outbox checkpoint?" — "Publish first, then checkpoint. A crash in between may duplicate the publish, which the guarded claim absorbs. Checkpoint-first could strand a queued Job with no broker message. An ambiguous publish outcome is not success — I retain the event and accept at-least-once delivery. And I reuse Day40 delivery semantics on a supported Celery broker transport; I don't reimplement Redis Streams consumer groups or hand-build a Celery replacement."

Review-round hardening (F1-F5): (F1) a lease-expiry/redelivery re-claim on an Attempt that already recorded a provider_request_id is RECONCILE_ONLY (Job -> PENDING_RECONCILIATION), never a second Provider call; (F2) a durable cancellation intent persisted after the RUNNING guarded claim is caught by a post-claim, pre-Provider re-check (zero calls, guarded terminal) — not just the QUEUED path; (F3) the provider_request_id event is attributed to the real parent Job (attempt_id->job_id) with attempt_id/provider_request_id/correlation_id evidence; (F4) the affected set is bounded by release + a time window (running_since) + running evidence, excluding out-of-window same-release running Jobs; (F5) the published invariant celery_task_id == job_id makes revoke target the correct task while the durable intent remains sole authority. P1 recovery-gap fix: a CONSERVATIVE durable marker (provider_dispatch_started_at) is persisted BEFORE the Provider request leaves the process (order: guarded claim -> marker -> Provider call -> record provider_request_id -> validate/terminal). A redelivery reconciles when the Attempt has EITHER a provider_request_id (strong evidence) OR the marker (conservative evidence); a Worker can OOM after dispatch but before recording the id, so a MISSING request id does NOT prove the Provider did not execute. Accepted safety-first false positive (marker set, request maybe not sent) -> reconcile, never retry; a provider idempotency key reduces risk but is not a reason to treat unknown external execution as a safe retry.

Validation: in-memory control-flow model — standard-library control flow; the guarded completion REUSES Day53's pydantic-backed strict validation gate (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 40 passed; full api suite 388). Proves application control flow only. NOT a real Celery broker/Worker, NOT real ACK/redelivery/visibility-timeout, NOT Worker-loss/OOM fault injection, NOT real PostgreSQL/Redis, NOT the real Provider. Day56 retry/backoff/rate-limit/cost/backpressure and Day57 integration/failure-injection suite are not implemented. No real credentials, prompts, Document content, or raw Provider tokens are used.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day55), the
[Day55 lesson](../docs/fastapi/day55-celery-worker-execution-and-long-running-ai-jobs.md), the
[Day55 design/runbook](../projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md),
the [model](../projects/ai-backend-data-layer/api/day55_celery_worker_execution.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day55_celery_worker_execution.py).

## Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure

Key vocabulary: retry storm / thundering herd, exponential backoff, full jitter, Retry-After, rate permit, shared limiter, fail closed, cost reservation, worst-case cost, settle/release, backpressure, admission control, execution certainty, circuit breaker, half-open probe, defer budget, business deadline, reconcile.

Useful expressions: "A guarded claim is execution authority; a rate permit is fleet capacity — both are required." · "No permit before a call is a durable defer, not a failure." · "A 429 alone is not proof nothing executed; unknown execution reconciles."

### Q1 (Beginner) — What is a retry storm and how do you prevent it?

Strong answer: "It's failed requests retrying together and re-amplifying the dependency — a thundering herd, not a cache avalanche (that's cache expiry loading the backend). I use bounded exponential backoff with full jitter and treat Retry-After as an earliest retry time, not a signal for every Worker to wake at the same instant." (Student's own: "不应该会导致缓存雪崩" — saw the amplification, used the wrong term.)

### Q2 (Intermediate) — A Worker holds the guarded claim. Why might it still not call the Provider?

Strong answer: "The claim is only per-Job execution authority. The call also needs fleet capacity from a shared rate limiter, an intact worst-case cost reservation, and a closed circuit for the Provider's failure domain. If any is missing and no call was made, it's a durable defer — persist next_attempt_at, reason, defer_count, and a deadline, and release the Worker; don't sleep in the Worker and don't mark the Job failed or pending reconciliation. A defer consumes no execution-retry budget. If the shared limiter store is down, I fail closed for new paid calls because I've lost the only cross-Worker concurrency bound." Weak answer: "It won the claim, so it can call."

### Q3 (Intermediate) — How do you reserve budget for a billable Job, and where does unused money go?

Strong answer: "Reserve the bounded worst-case cost at acceptance from the persisted contract — max_tokens times unit price — not the remaining balance. If the tenant can't cover the worst case, don't accept or call. On success I settle the actual usage and release the unused remainder back to the durable tenant cost ledger, not to the rate limiter — capacity and money are different resources." (Student corrections: "500 token" remaining-budget → worst-case; "应该回归到limiter" → returns to the tenant ledger.)

### Q4 (Senior) — Classify a Provider 429 and design circuit recovery.

Strong answer: "A 429 alone is not universal proof nothing executed. The Adapter classifies execution certainty: definitely-not-accepted (safe to ordinary-defer/retry), may-have-executed, or unknown — retaining a provider request id when available. Only definitely-not-accepted can retry; unknown or evidence reconciles, so I never double-bill. A circuit breaker protects the Provider failure domain keyed by provider/account/model/region with no secrets: CLOSED allows, OPEN durably defers new calls, HALF_OPEN allows a small progressive probe set. A single successful probe doesn't close the circuit or release all deferred Jobs — recovery is gradual." (Student: "暂时停止向该 Provider 发起新的调用", "不能，应该少量的受控渐进恢复".)

### Q5 (Senior) — A bad release set max defer to zero and expired capacity-deferred Jobs. Recover.

Strong answer: "Roll the configuration back first to stop future harm — that is not a business-fact rollback, it doesn't repair Jobs already committed EXPIRED. Then build a bounded affected set from the release version, a time window, the capacity expiry reason, and Attempt/Event evidence, and preserve the expired history — never bulk-flip to queued. Re-dispatch only Jobs with proof of no Provider execution and a still-valid contract, deadline, and budget, via a guarded, audited repair that writes a new durable Outbox dispatch intent for the Relay to publish after commit — never a direct queue call, which would reintroduce a dual-write failure. Jobs with any Provider evidence are reconcile-only." (Student: "第一步回滚错误配置，第二步修复持久化的job", "写入一个新的 durable Outbox dispatch intent 再由 Relay 发布".)

Production scenario / trade-off prompt: "Where does backpressure live, and can a Worker shrink max_tokens under load?" — "Backpressure lives before the durable Job + Outbox commit: a tenant over its own quota gets 429, system-wide unavailability gets 503, and I never return 202 for a commitment I can't keep or retroactively convert an accepted Job to 429/503. A Worker never silently reduces persisted model or max_tokens; degradation is allowed only if the persisted, product-authorized contract permits it, down to a floor." (Student: "创建 Job 之前拒绝/限速该请求", "不能，worker只是执行者".)

Validation: in-memory control-flow model — standard-library only, imports Day54 IntentKind (Python 3.10.12, pytest 7.4.3 -> 31 passed; full api suite 419). Proves application control flow only. NOT a real Celery broker/Worker, NOT a real Redis distributed limiter/circuit, NOT real PostgreSQL, NOT real Provider traffic/rate limits/costs, NOT load, NOT Worker-kill fault injection, NOT production. Day57 integration/failure-injection and Day58 observability are not implemented. No real credentials, prompts, Document content, raw Provider payloads, or secrets are used.

Pair with [`cheat_sheets/fastapi.md`](../cheat_sheets/fastapi.md) (Day56), the
[Day56 lesson](../docs/fastapi/day56-provider-resilience-rate-limits-token-cost-and-backpressure.md), the
[Day56 design/runbook](../projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md),
the [model](../projects/ai-backend-data-layer/api/day56_provider_resilience.py), and the
[tests](../projects/ai-backend-data-layer/api/test_day56_provider_resilience.py).
