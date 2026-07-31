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
pytest 7.4.3 -> 13 passed). PostgreSQL runtime NOT RUN (no server/driver; SQLite is not PostgreSQL evidence).
FastAPI/Worker integration, real Provider, Object Storage, production NOT RUN. Alembic = Day48; upload = Day49;
acceptance/Outbox = Day50.
