# Lesson 45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Advanced

Estimated Time: 7-8 hours

Prerequisite: Day44 — Pydantic v2 and Structured AI Input/Output Contracts

Previous Lesson: [Day44 — Pydantic v2 and Structured AI Input/Output Contracts](day44-pydantic-v2-and-structured-ai-input-output-contracts.md)

Next Lesson: Day46 — SQLAlchemy 2.0 Mapping for the Day42 Data Model (planned — Phase 4; see [CURRICULUM.md](../../CURRICULUM.md) and [ROADMAP.md](../../ROADMAP.md); the Day46 lesson file does not exist yet)

Phase: Phase 4 — Production AI API Engineering

Engineering Artifact: The Day45 composition design ([`projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md`](../../projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md)) with runnable code [`day45_composition.py`](../../projects/ai-backend-data-layer/api/day45_composition.py) and tests [`test_day45_composition.py`](../../projects/ai-backend-data-layer/api/test_day45_composition.py) — validated secret-aware `Settings`, a small `AIProvider` protocol, a production adapter + `FakeAIProvider` seam, `create_app` + a lifespan `Container` that closes resources in reverse order, `get_provider`, a stateless `JobService`, and Day44 Provider-output validation before an illustrative in-memory completion. Real local FastAPI composition tests were executed (12 passed; Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3) with a FAKE no-network Provider; real Provider SDK/network, PostgreSQL, SQLAlchemy, Celery/Redis, and production are NOT RUN — see [projects/ai-backend-data-layer/README.md](../../projects/ai-backend-data-layer/README.md)

FastAPI Cheat Sheet: [cheat_sheets/fastapi.md](../../cheat_sheets/fastapi.md)

FastAPI Interview: [interview/fastapi.md](../../interview/fastapi.md)

Estimated Study Time:

```text
Reading: 150-180 minutes
Exercises + running the tests: 110-140 minutes
Hands-on composition/lifespan design: 90-120 minutes
Review: 30-45 minutes

Total: 7-8 hours
```

---

# Learning Objectives

By the end of this lesson you can:

1. Explain why resource ownership is per-process, and decide which processes (API vs Worker) create a Provider client.
2. Distinguish app/process scope from request/Job scope, and place Settings, the HTTP client, and the Provider adapter in the lifespan rather than in a Router.
3. Explain why `Depends()` supplies an already-created dependency and does not create an app-wide or cross-process singleton.
4. Design a validated, secret-aware `Settings` boundary and explain why an API key never lives in Router code or a Job payload.
5. Choose a fail-fast startup policy for missing/invalid configuration, and explain why startup must not issue a paid Provider generation call.
6. Design safe, allowlisted configuration-error logging that never emits a Secret, prompt, tenant data, or raw vendor output.
7. Diagnose import-time construction and move it into an explicit `create_app` / Composition Root.
8. Design partial-initialization cleanup that closes the already-created resource, publishes no Container/readiness, and claims no Job.
9. Define a small `AIProvider` seam with a production adapter and a `FakeAIProvider`, and translate vendor exceptions into stable application errors.
10. Write composition tests with `create_app`, a fake factory, and FastAPI dependency overrides configured before `TestClient` lifespan startup — asserting the effect, not just the exception.
11. Sequence a safe Settings rotation and a graceful Worker drain, and recover from an interrupted Provider call without blind requeue/replay — distinguishing code/config rollback from durable-fact repair.

---

# Why This Matters

Day44 made the Day43 contract executable, but it deliberately stopped at one question and never answered the
next one: **who creates the objects?** Who builds the `Settings`, the HTTP client, and the Provider client;
who closes them; how a production implementation and a Fake are substituted; and how the typed contracts enter
a Worker execution path. Day45 is that composition boundary.

The scenario is a real anti-pattern. A multi-tenant AI Job API already has Day44 contracts, but a Router
constructs an AI Provider SDK client **on every request** and reads `PROVIDER_API_KEY` **directly from the
environment** inside HTTP code. Four things break at once: connection churn (a new client per request throws
away pooled connections), Secret/infrastructure knowledge leaks into HTTP handlers, you cannot inject a fake so
tests are forced onto the network and cost money, and there is no controlled shutdown to drain in-flight work
or close the client. Every one of those is a production incident waiting for load.

Day45 fixes it by drawing an ownership line. **Settings** are validated, secret-aware input to a process.
**Lifespan** creates and closes application/process-scoped resources exactly once. **`Depends`** supplies
already-created interfaces. **Stateless services** are created per request/Job. Each **Worker process** owns
its own Provider client and drains before shutdown. Provider output remains untrusted until Day44 validation
succeeds immediately before a future guarded completion. And a **release/config rollback protects future
executions**, while already-started Provider calls and committed facts require a separate, correlated,
idempotent, audited recovery.

This lesson has **real local runtime evidence**: a minimal FastAPI composition with a lifespan `Container` and
a **fake, no-network** Provider was executed — **12 pytest cases passed** on Python 3.10.12 / fastapi 0.110.0 /
httpx 0.27.0 / pydantic 2.5.0 / pytest 7.4.3. But the completion target is an **in-memory list, not
PostgreSQL**, and a **real Provider SDK/network**, PostgreSQL, SQLAlchemy/Alembic, Celery/Redis/Object Storage,
Secret rotation/drain, and production are all **NOT RUN**. Those are later lessons.

---

# Roadmap Position

```text
Day42 durable data ownership + failure contract
Day43 HTTP product contract + request lifecycle
Day44 executable Pydantic v2 boundary contracts
Day45 DI + lifespan + configuration + Provider adapter seam   <-- you are here
Day46 SQLAlchemy 2.0 persistence mapping (no ORM/public-model merge)
Day47 async session lifecycle, transaction, repository, unit of work
```

Knowledge continuity:

```text
Previous knowledge
  Day44 typed request/response/Provider contracts and the boundary ladder; Day44's rule that Provider output
  is fully untrusted and must be validated before any completion side effect; code rollback != DB rollback
        |
        v
Current lesson
  compose those contracts into a runnable FastAPI/Worker: validated secret-aware Settings, a lifespan that owns
  app-scoped resources, Depends() that supplies them, a small AIProvider seam with a Fake, and validation
  before an illustrative completion — with real local fake-runtime tests
        |
        v
Future production usage
  Day46 maps the Day42 durable model with SQLAlchemy WITHOUT merging ORM and public Pydantic models, using this
  dependency boundary; Day47 adds request-scoped AsyncSession/transaction/unit-of-work (distinct from the
  app-scoped Provider); Day50 attaches the idempotent Job+Outbox acceptance path; Day53 implements a real
  OpenAI-compatible SDK behind this AIProvider seam; Day54 streaming/cancellation; Day55 Celery drain/ACK/
  recovery; Day56 retries/rate limits/cost/backpressure
```

Day45 does **not** implement Day46 SQLAlchemy mappings, Day47 sessions/transactions, Day50 Outbox, Day53 a real
SDK, Day54 cancellation, Day55 Celery, or Day56 retry/backpressure. They are named only as future connections.

---

# Lesson Map

```text
1.  Ownership is per-process       -> Worker owns Provider work, but "Worker owns it" != one global client
2.  DI and scopes                   -> lifespan owns app-scoped resources; Depends supplies; JobService per request
3.  Settings + secrets boundary     -> validated Settings; SecretStr reduces display, is not encryption
4.  Fail-fast startup               -> invalid config -> not ready, no claim; no paid generation on startup
5.  Safe configuration logging      -> allowlisted redacted events; never Secret/prompt/tenant/raw output
6.  Import time vs composition root  -> no module-scope construction; create_app receives Settings + factories
7.  Partial-initialization cleanup   -> close the created client, publish no Container/readiness, no claim
8.  Provider adapter seam            -> small AIProvider protocol; production adapter + FakeAIProvider; error translation
9.  Test composition                 -> create_app + fake factory + dependency_overrides BEFORE TestClient; test the effect
10. Rotation / drain / rollback       -> verify new before draining old; drain then close; code rollback != DB rollback
11. Invalid-Provider-output incident   -> contain / preserve / roll back code / classify / guarded audited recovery
```

---

# Core Mental Model

```text
Composition boundary = the ONE place infrastructure is created and closed.

  import time         -> declare types/routes only (no Settings/client/adapter at module scope)
  create_app(settings, factories)
  lifespan (app/process scope):
      Settings(validated) -> async HTTP client -> ProviderAdapter -> PUBLISH Container
      -> yield ready -> clear container -> close resources (REVERSE creation order)
  Depends()            -> SUPPLIES already-created interfaces (request-local cache; NOT a cross-process singleton)
  JobService           -> stateless, per request/Job
  Worker Service       -> validates raw Provider JSON via Day44 BEFORE any completion

Scopes:      app/process (Settings, HTTP client, ProviderAdapter)   vs   request/Job (JobService, later AsyncSession)
Secrets:     Settings is the secret boundary; SecretStr hides display, is NOT encryption; keys never in payloads/logs
Fail-fast:   invalid LOCAL config -> not ready -> no claim  (local validity != external Provider availability)
Rotation:    start+verify NEW -> drain OLD -> close OLD; never drain healthy old before new is ready
Recovery:    code/config rollback protects the FUTURE; interrupted calls + committed facts need audited repair
```

---

# Main Concepts

## Concept 1: Ownership is per-process — "the Worker owns it" is not "one global client"

### Tech Lead Question

An AI Provider call can take eight minutes. A Router builds a Provider SDK client on every request. Who should
own that long-running Provider execution, and how many Provider clients exist across 4 API processes and 8
Worker processes?

### Student Thinking

The student immediately rejected the Router owning an eight-minute call and reached for the Worker, then
reasoned about per-process clients and how a long-lived global client relates to connections.

### Student Answer

> "不会，我觉得应该由worker来做吧"

> "每个worker进程各一个，全局client长期占用数据库连接"

### Tech Lead Review

The first instinct is right: a durable, long-running Provider call belongs to a **Worker**, not an HTTP Router
that should answer quickly. And "每个 worker 进程各一个" is the correct shape — **resource ownership is
per-process**. But two refinements. First, "Worker owns it" does not mean one global client: **only processes
that actually call the Provider create one**. An API process that never calls the Provider should not create a
Provider client; a Worker that does creates and closes **its own** client in **its own** lifespan; a future
synchronous/streaming API process that calls the Provider owns a **separate** client too. With 8 Worker
processes you have **8 independent app-scoped clients** — separate memory, no cross-process Python global.
Second, the correction to "占用数据库连接": a Provider client normally holds **HTTP connections/pools**, **not**
database connections. Database sessions/pools are a **Day47** concern, and conflating the two is a common trap.

### Engineering Thinking

A process should own exactly the resources it uses. Pushing long Provider work to a Worker keeps HTTP acceptance
short (the Day43 commit-before-202 shape), and per-process ownership means startup/shutdown can create and close
each client deterministically.

### Production Example

Eight Worker replicas each hold their own pooled HTTP client to the Provider; an autoscaler adds a ninth
replica, which starts its own client at startup and closes it at shutdown. No shared global object exists to
leak or double-close across processes.

### Framework Connection

FastAPI/Starlette lifespan runs once per process; a Worker (later Celery, Day55) has its own process lifecycle.
The HTTP client (an async `httpx.AsyncClient` in production) is process/app scoped.

## Concept 2: Dependency injection and scopes

### Tech Lead Question

Where does the shared Provider client live, and what exactly does `Depends()` give you? Should a stateless
`JobService` be a singleton or created per request?

### Student Thinking

The student separated the long-lived client from the per-request service and noticed that one Worker
asynchronously claims many Jobs, so the client's lifetime is not a single Job's lifetime.

### Student Answer

> (Provider client vs JobService scope) "每个请求/Job 轻量创建"

> (may a Job handler close the shared client?) "不用，一个worker可以异步claim多个job，lifespan不是随着job结束的"

### Tech Lead Review

Both correct. A stateless `JobService` that only receives an `AIProvider` is **lightweight and created per
request/Job**; it must not carry tenant/trace/job-local state between executions. The **Provider client belongs
to app scope**, created once in the lifespan — and "一个 worker 可以异步 claim 多个 job，lifespan 不是随着 job 结束的"
is exactly why a Job handler must **not** close the shared client. The piece to name precisely: `Depends()`
**supplies an already-created dependency**; it does **not** itself make an app-wide or cross-process singleton,
and FastAPI's default dependency cache is **within one request's dependency graph**, not across requests or
processes. So `get_provider` should **return the lifespan-created `AIProvider`**, not construct a new adapter
per resolution. A `yield` dependency fits a **request-scoped** resource (Day47's `AsyncSession`), **not**
closing a shared app-scoped adapter at every request end.

### Engineering Thinking

Match lifetime to scope: create expensive, closeable things once (lifespan), hand them out by reference
(`Depends`), and keep per-request objects cheap and stateless so concurrency is safe.

### Production Example

`get_provider` reads `request.app.state.container.provider` and returns it; 200 concurrent requests share one
pooled client instead of building 200 clients and 200 connection pools.

### Framework Connection

`Depends`, `Request.app.state`, and the request-local dependency cache; contrast with the lifespan that owns the
app-level closeable resource.

## Concept 3: Settings and the secrets boundary

### Tech Lead Question

Where does the API key come from, and is `SecretStr` a security guarantee?

### Student Thinking

The student identified validated Settings as the boundary and noted payloads are an unsafe place for keys, then
described what a `SecretStr` actually is.

### Student Answer

> "经过校验的 Settings 对象，router、Worker Job payload传输不安全"

> (what does SecretStr guarantee?) "Secret类型，不是明文的"

### Tech Lead Review

Right on the boundary: the API key and provider configuration must come from **validated Settings**, never
Router code and **never** Job payloads — payloads may be persisted, replayed, and logged, so a key in a payload
is a leak. The `SecretStr` answer needs sharpening: `SecretStr` **reduces accidental printing/repr/serialization
exposure**, but it is **not encryption in process memory** and does not prevent a deliberate
`get_secret_value()` log, an environment-permission mistake, or bad network/Secret-store security. The Adapter
construction boundary is the controlled place that obtains the real secret value; Router, Job payload, public
errors, and routine logs never receive it. Required startup validation examples: a **non-empty API key**, a
**valid provider base URL**, a **configured model**, and a **positive, bounded timeout**.

### Engineering Thinking

Configuration is validated input to a process, exactly like a request is validated input to a handler. Keeping
the Secret behind a `SecretStr` at a single construction boundary shrinks the blast radius of an accidental log
line — but it is a hygiene tool, not a vault.

### Production Example

`Settings` exposes `safe_log_fields()` returning `{provider_base_url, provider_model, request_timeout_s,
provider_api_key: "***REDACTED***"}`; the raw key is only read at adapter construction.

### Framework Connection

Pydantic v2 `BaseModel` + `SecretStr` + `field_validator`; a compatible settings mechanism (do not assume a
specific package version without inspecting dependencies).

## Concept 4: Fail-fast startup — and do not pay to test a key

### Tech Lead Question

The new deployment is missing a valid Provider API key. What should the Worker do at startup? Should startup
send a generation request to prove the key works?

### Student Thinking

The student chose to fail immediately to keep the cost of the error small, and separately refused to spend money
probing the key at startup.

### Student Answer

> (missing/invalid Settings) "启动即失败，错误成本小一些"

> (send a paid generation call to test the key?) "不会，这样太消耗成本了"

### Tech Lead Review

Both correct. A Worker must **fail fast** on missing/invalid local configuration, **remain not ready**, and
**not claim Jobs** — failing at startup is far cheaper than beginning work with known-invalid config. The nuance
to keep honest: local Settings validation is **not proof that the external Provider is currently available**;
it only proves the local config is well-formed. And "不会，这样太消耗成本了" is the right call — do **not** send a
paid generation call on startup merely to test a key. A cheap, no-side-effect Provider health endpoint **may**
be a separately designed, bounded check if one exists, but it still **cannot** prove later generation success;
runtime Provider failures remain runtime failures.

### Engineering Thinking

Fail-fast turns a slow, expensive, mid-Job failure into a fast, cheap, at-startup failure. But readiness is
about *local* correctness; do not overclaim that a green startup guarantees the remote Provider will answer.

### Production Example

A Worker whose `PROVIDER_API_KEY` is empty raises a `ValidationError` during `Settings.load()`, never publishes
readiness, and the orchestrator keeps the old healthy replicas serving.

### Framework Connection

Pydantic `ValidationError` at `Settings.load()`; a readiness/`/healthz` gate that reflects whether the Container
was published.

## Concept 5: Safe configuration logging

### Tech Lead Question

Configuration validation failed. What do you log?

### Student Thinking

The student first said to log the adapter's returned error, then corrected toward metadata rather than raw
content.

### Student Answer

> "要记录Adapter返回的错误，不能记录API key、prompt、租户数据或原始 Provider 内容"

> (safe config-error shape) "不能，用其他的错误类型展示代替详细信息"

### Tech Lead Review

The allowlist instinct is right, with one correction: do **not** routine-log the **raw** Adapter/vendor error
body either — classify and mask it. Log an **allowlisted, redacted event**: `event=config_validation_failed`,
`field=provider_api_key`, a stable `code`, the component, and the settings/deployment version. Never log the API
key, Authorization headers, complete prompts, tenant-sensitive data, raw Provider output, or raw vendor error
bodies, and never dump whole `Settings` or a raw `model_dump()`. "用其他的错误类型展示代替详细信息" is exactly the
safe pattern: a stable error class plus correlation metadata, not the sensitive detail.

### Engineering Thinking

Logs are durable and widely readable. Treat them as another boundary that must be allowlisted, so a debugging
convenience never becomes a Secret disclosure.

### Production Example

`log.warning(event="config_validation_failed", field="provider_api_key", code="CONFIG_INVALID",
component="worker", settings_version="2026-07-29.3")` — enough to debug, nothing sensitive.

### Framework Connection

Structured logging with an allowlist; the same discipline as the Day44 `PublicErrorResponse` (never leak SQL/
tracebacks/credentials/raw Provider errors).

## Concept 6: Import time vs the composition root

### Tech Lead Question

A module constructs `Settings` and an `OpenAICompatibleAdapter` at module scope, on import. What breaks, and
where should construction move?

### Student Thinking

The student reasoned that construction should be explicit and testable, at a composition root rather than at
import.

### Student Answer

> "由 create_app() / Composition Root 显式接收或构造"

### Tech Lead Review

Correct. **Import time should declare types, routes, and functions only** — no `Settings`, Provider clients, or
adapters at module scope. Module-level construction makes tests fail **during import**, before fakes can be
injected; gives poor startup/readiness classification; and has no dependable resource-close pairing. The
**Composition Root / `create_app()`** receives or constructs `Settings` and factories **explicitly**, and the
**lifespan** creates resources and publishes a `Container` **only after complete initialization succeeds**. That
is what makes the whole system testable with fakes.

### Engineering Thinking

Construction is a side effect; keeping it out of import means importing the module is always safe, and every
resource has one clear creation site and one clear close site.

### Production Example

`create_app(settings, http_client_factory=..., provider_factory=...)` builds the app; tests pass fake factories,
production passes real ones. Nothing is created merely by importing `day45_composition`.

### Framework Connection

FastAPI application factory + `asynccontextmanager` lifespan; `app.state` holds the published `Container`.

## Concept 7: Partial-initialization cleanup

### Tech Lead Question

During startup the async HTTP client is created successfully, but the Provider adapter fails to initialize
before readiness. What must happen? (This was taught directly.)

### Student Thinking

The student did not initially know the cleanup design and, in an earlier framing, proposed only cancelling the
client creation.

### Student Answer

> (partial-initialization cleanup) "不知道"

> (earlier attempt) "断言创建HTTP client取消"

### Tech Lead Review

Honest "不知道" — here is the pattern. If the HTTP client was created but adapter init fails, the
**already-created HTTP client must be closed**, **no Container/Provider is published**, and the **Worker must
not claim a Job**. So the assertion is not "the client's creation was cancelled" (it *was* created) but that the
**already-created client is closed**, readiness is **not** published, and no work is claimed. Resources are
released in **reverse creation order**, expressed with `try/finally`, `asynccontextmanager`, `AsyncExitStack`,
or a correct async context-manager structure. The conceptual pattern: `Settings validation -> async HTTP client
-> ProviderAdapter -> publish Container -> yield ready -> clear container -> close resources`.

### Engineering Thinking

Startup is a transaction: either the whole Container is published, or every resource created so far is closed
and nothing is published. A half-initialized process that claims work is worse than a process that never
started.

### Production Example

`test_partial_init_closes_client_and_no_readiness` builds an app whose provider factory raises; entering the
`TestClient` raises during startup, and the test asserts the tracking client was **closed**, the Container is
**not** published, and no completion happened.

### Framework Connection

`asynccontextmanager` lifespan with `try/except` around adapter creation that closes the client and re-raises.

## Concept 8: The AI Provider adapter seam

### Tech Lead Question

Should `JobService` depend on the vendor SDK or on an interface? How do vendor errors and Provider output cross
the boundary?

### Student Thinking

The student chose an interface dependency for replaceability, picked a fake for no-cost tests, and located both
the error-translation boundary and the Day44 validation point.

### Student Answer

> (interface vs SDK) "依赖AIProvider，因为可以更方便替换"

> (deterministic tests) "注入 FakeAIProvider，无成本测试"

> (vendor errors) "由 AIProvider Adapter 转换成自己的稳定错误类型"

> (where is Provider output validated?) "Worker Service 的'完成 Job 前'边界"

### Tech Lead Review

All correct, and together they define the seam. `JobService` depends on a **small `AIProvider`
protocol/interface**, not a concrete vendor SDK — which is exactly what makes it replaceable. The production
`OpenAICompatibleAdapter` hides SDK initialization, request construction, vendor response extraction, the HTTP
client ownership boundary, and vendor-specific exceptions, and it **translates vendor exceptions into stable
application errors** (`ProviderTimeout`, `ProviderRateLimited`, `ProviderAuthentication`,
`ProviderTransport`). The `FakeAIProvider` returns deterministic valid/invalid JSON or raises a deterministic
classified error, giving **no-network/no-cost** tests. Keep the interface **small** — do not leak the vendor
SDK's types/parameters into services. And "Worker Service 的'完成 Job 前'边界" is exactly right: the Worker
Service validates raw Provider JSON through Day44's `StructuredAIResult.model_validate_json(...)` **before any
future guarded completion**. The Router validates client HTTP input; it is **not** the boundary for a Worker
Provider result. The Adapter classifies/masks vendor detail; **Day56** owns retry/backoff/cost/backpressure
policy, not this lesson.

### Engineering Thinking

An interface seam turns "our code depends on OpenAI" into "our code depends on `AIProvider`, and one adapter
depends on OpenAI." Vendor drift and test doubles both stop at that one small surface.

### Production Example

`OpenAICompatibleAdapter` maps a vendor 429 to `ProviderRateLimited`; a test injects
`FakeAIProvider(raw_json=...)` and never touches the network. Day53 implements the real SDK behind the same
`AIProvider`.

### Framework Connection

A `typing.Protocol` for `AIProvider`; the Day44 `StructuredAIResult` reused for output validation before
completion.

## Concept 9: Testing composition and validation boundaries

### Tech Lead Question

How do you test all of this without creating a real Provider client during lifespan startup? Where do fakes and
overrides go, and when do you configure them? (The first executable fake-runtime test was taught directly.)

### Student Thinking

The student knew the override mechanism and the timing, and correctly described the `TestClient` resource
lifecycle, but did not initially know the full first-test design.

### Student Answer

> (use-site substitution) "FastAPI 的 dependency override"

> (when to configure fakes) "在进入TestClient之前"

> (client open/closed across the context) "未关闭，退出后关闭"

> (first executable fake-runtime test) "不知道"

### Tech Lead Review

The three known answers are all correct: use **FastAPI dependency overrides** for use-site substitution of
`get_provider`; configure fakes/overrides **before entering `TestClient`**, because its context triggers
**lifespan startup**; and the shared client is **open inside the context and closed after exit** (not closed per
request). One caution: an **override alone does not prevent a lifespan from creating a real resource** — you
also compose with `create_app(test_settings, fake_adapter_factory)` so startup never builds a real client. Here
is the "不知道" first-test design: use **fake Settings / a fake Secret value**, a **tracking HTTP client** that
records whether it was closed, a **fake Adapter/Provider factory**; **enter** the `TestClient`/lifespan, make a
**deterministic** request, then **exit**; and assert **no network**, the **Fake Provider was used**, the
**resource is open inside** the context, the **resource is closed after** exit, and **no Secret** appears in
result/log assertions. Clear overrides after tests. And reuse Day44's principle — **test the effect, not only
the exception**.

### Engineering Thinking

The composition seam exists so tests can substitute infrastructure deterministically. A test that asserts the
*effect* (client closed, completion list empty, no network) proves behavior a "did it raise?" test cannot.

### Production Example

`test_fake_provider_injected_no_network_and_client_lifecycle` enters the `TestClient`, asserts the tracking
client is open and the Container published, posts a job, then after exit asserts the client is closed, no
network occurred, and the fake was used exactly once.

### Framework Connection

`fastapi.testclient.TestClient` (context manager triggers lifespan), `app.dependency_overrides`, and a tracking
fake client with an `aclose()` recorder.

## Concept 10: Configuration rotation, graceful drain, and rollback

### Tech Lead Question

You must rotate the Provider Secret. Do you hot-swap `app.state.provider` and close the old adapter immediately?
A new deployment's config is invalid — do you drain the old Workers first? What is the correct shutdown
ordering?

### Student Thinking

The student worked through several framings — first about admission/rollout, then correcting toward in-flight
references and the readiness-before-drain rule, and gave a correct drain/close ordering.

### Student Answer

> (rollout order) "不会，应该contain已经运行的worker进程接受新的job admission，brain正在运行的worker，删除旧的worker进程，保证新的worker全使用新配置"

> (invalid new config) "先停止新版本worker继续接受新job，再回滚新版本"

> (in-process hot swap) "不能，新的无法工作，但 旧的已停止消费，队列积压且服务容量被人为清空。"

> (graceful shutdown ordering) "先停止 claim 新 Job、等待/处理 in-flight Job，再关闭 client，因为provider的调用并没有停止，之后会返回错误的artifact，以及其他副作用"

### Tech Lead Review

The shutdown **ordering** is exactly right: **stop claiming new Jobs first**, **wait/handle in-flight work**
under a bounded drain, **then close** the Provider client — never close it first (with one correction below on
the "错误的 artifact" wording). The rotation sequence needs the readiness-before-drain rule made explicit.
Settings/Container should be **immutable for one process lifecycle**; do **not** hot-swap `app.state.provider`
and immediately close the old Adapter, because **in-flight Job handlers still hold the old reference** while
newer handlers use the new one — that is the real problem, not just a rollout-capacity gap. Prefer **controlled
process replacement**: (1) start new Worker processes with new config; (2) require successful local
startup/readiness; (3) **only then** drain old Workers so they stop claiming new Jobs; (4) allow in-flight Jobs
a **bounded** drain window; (5) close the old Adapter/client and terminate the old process; (6) verify no old
settings version remains and correlation/error evidence is healthy. If the new config is invalid, **keep old
Workers operating** and roll back/fix the new deployment — never drain healthy old Workers before new Workers
prove ready. And code/config rollback is **not** a PostgreSQL rollback. One correction to the shutdown wording:
if a drain deadline hits while a Provider call is in progress, the external result state may be **unknown** — it
is not necessarily a "错误的 artifact"; do not blindly requeue it, because the external call may have run, cost
money, or return later (Day34 lease/fencing, Day40 at-least-once, Day55 recovery govern the guarded path).

### Engineering Thinking

Availability during change comes from **overlap**: prove the new thing works before you remove the old thing,
and drain rather than yank. Immutability per process removes a whole class of "half old, half new" bugs.

### Production Example

A Secret rotation starts 8 new Workers, waits for all to report ready, drains the 8 old Workers over a bounded
window, then terminates them — with a rollback path that keeps the old Workers if the new ones fail readiness.

### Framework Connection

Process-level orchestration (later Celery/Day55 for real drain/ACK/recovery); lifespan shutdown ordering; Day34
lease/fencing and Day40 at-least-once for interrupted-call recovery.

## Concept 11: The integrated invalid-Provider-output incident

### Tech Lead Question

A new Provider Adapter release starts normally and claims Jobs, but a vendor response-format change produces
invalid JSON. Day44 validation blocks completion. Some Jobs already called the Provider. Contain, preserve, roll
back, classify, recover, and prevent recurrence — and can you blindly requeue after a forced stop?

### Student Thinking

The student refused a blind requeue and reasoned about double calls, wasted cost, and audit traceability.

### Student Answer

> (blind requeue after a forced stop?) "不能，因为这会导致二次调用，成本浪费，让审计记录不可追溯"

### Tech Lead Review

The refusal is correct and for the right reasons. **Contain**: stop the affected Worker release from claiming
new Jobs and route execution to a known-good version while retaining correct drain behavior. **Preserve**:
release version, settings version (**never** the Secret), provider/model, job/attempt/request/trace IDs, error
category, time window, and secure references to the original output/audit evidence. **Roll back**: application
code/configuration only, deploying a healthy Worker first — do **not** claim database history rolled back.
**Classify** by release/time/attempt/output evidence; validation-before-completion does **not** prove an
external Provider call never happened. **Recover** with an **idempotent, guarded, audited** process **only
after** Provider correlation/idempotency evidence is checked, reconciling Job/Attempt/Event/Artifact records.
**Never** blindly requeue/replay paid calls, mark raw invalid JSON as succeeded, delete audit evidence,
fabricate a Result Artifact, or write Secrets/prompt/raw output to routine logs. One sharpening of the
student's reason: the audit history does not disappear on its own, but a **blind state mutation/replay destroys
explainability** and can double-spend — which is why recovery must be correlated and guarded.

### Engineering Thinking

Validation blocking completion is the safety net that keeps invalid output from becoming a false `succeeded`,
but the interrupted external calls and any committed facts are a **separate** recovery problem that needs
correlation and idempotency — not a rerun.

### Production Example

The bad release is quarantined, traffic routes to the previous adapter, the affected Jobs are classified by
release window and attempt records, and only confirmed cases are repaired through an audited, idempotent
operation — no paid Provider call is replayed blindly.

### Framework Connection

Day44 `model_validate_json` as the completion gate; Day34 lease/fencing, Day40 at-least-once delivery, and Day55
Worker recovery for the guarded/audited reconciliation.

---

# Common Misconceptions

"The Worker owns it" means one global client

❌ "Push the Provider to the Worker, so one global Worker client serves everything."
✅ Ownership is per-process: only processes that call the Provider create one; 8 Workers = 8 independent
app-scoped clients, and a Provider client holds HTTP connections, not database connections.

Why beginners think this: "move it to the Worker" sounds like "one Worker owns one client."
How to remember: each process owns exactly the resources it uses.

`Depends()` creates a singleton

❌ "`Depends()` makes an app-wide (or cross-process) shared instance."
✅ `Depends()` supplies an already-created dependency; its default cache is request-local. The lifespan creates
the shared app-scoped resource; `get_provider` returns that instance.

Why beginners think this: DI frameworks often manage singletons.
How to remember: lifespan owns; `Depends` hands out.

`SecretStr` is security

❌ "`SecretStr` means the key is encrypted/safe."
✅ It reduces accidental printing/repr/serialization exposure only. It is not memory encryption and does not
replace permissions, rotation, or secure logging.

Why beginners think this: the type name says "secret."
How to remember: `SecretStr` hides display, not attackers.

A `yield` dependency should close the shared client

❌ "Close the Provider client in a `yield` dependency at request end."
✅ The shared client is lifespan-scoped; request-scoped `yield` cleanup fits Day47's `AsyncSession`, not a
shared app-scoped adapter.

Why beginners think this: `yield` cleanup looks like the place to close things.
How to remember: request cleanup closes request resources, not app resources.

Partial init only needs an exception (or "cancel the client")

❌ "If adapter init fails, just raise — or assert the client creation was cancelled."
✅ The already-created client must be **closed**, no Container/readiness is published, and no Job is claimed.
Assert those effects.

Why beginners think this: the exception feels like the whole story.
How to remember: startup is all-or-nothing; close what you created.

Configure fakes after entering `TestClient`

❌ "Set dependency overrides after creating the `TestClient`."
✅ `TestClient`'s context triggers lifespan startup; configure fakes/overrides **before** entering it, and an
override alone does not stop a lifespan from creating a real resource — compose with a fake factory too.

Why beginners think this: the client exists before the request.
How to remember: entering `TestClient` = startup; fakes must already be in place.

Drain old Workers, then start new ones

❌ "Stop the old Workers, then roll out the new config."
✅ Start and verify new Workers ready **first**; only then drain old ones. If the new config is invalid, keep
old Workers running and roll back.

Why beginners think this: "replace" sounds like "remove then add."
How to remember: prove the new before draining the old.

Close the Provider client first on shutdown

❌ "Shut down by closing the Provider client, then draining."
✅ Stop claiming new Jobs first, drain in-flight work under a bounded window, then close the client. Never close
it first.

Why beginners think this: closing the client feels like "stop."
How to remember: stop intake → drain → close.

Blindly requeue an interrupted Provider call

❌ "After a forced stop, requeue the Job to be safe."
✅ The external call may have run, cost money, or return later; blind replay double-spends and destroys
explainability. Recover with correlation, idempotency, guarded durable transitions, and audit.

Why beginners think this: requeue looks like a safe retry.
How to remember: an interrupted paid call is unknown, not free.

Code/config rollback rolls back the database

❌ "Roll back the release and the durable facts are fixed."
✅ Code/config rollback protects future executions; committed facts need a separate idempotent, guarded, audited
repair. Code rollback ≠ database-history rollback.

Why beginners think this: rollback sounds total.
How to remember: roll back code for the future; reconcile facts for the past.

---

# Engineering Trade-offs

## Lifespan-owned resource vs per-request construction

Constructing the Provider client per request is simple and stateless-looking but causes connection churn, leaks
Secret/infrastructure knowledge into HTTP code, blocks fakes, and has no controlled shutdown. A lifespan-owned
client costs a composition seam but gives pooling, testability, and deterministic close. For anything holding
connections, own it in the lifespan.

## Interface seam vs direct vendor SDK

A small `AIProvider` protocol costs an adapter and a mapping layer but isolates vendor drift and enables
no-cost fakes; depending on the SDK directly is less code but couples every service to vendor types and forces
network tests. For a boundary to an external paid API, pay for the seam.

## `extra="forbid"` + immutable Settings vs flexible config

Strict, frozen Settings reject unknown keys and prevent per-process mutation (a whole class of "half old, half
new" bugs) but require deliberate rollout for new fields; loose config is convenient but drifts silently. For a
security/config boundary, forbid and freeze.

## Fail-fast startup vs lazy/tolerant startup

Fail-fast keeps a broken process not-ready and cheap, but needs a readiness gate and orchestration; tolerant
startup keeps the process up but risks claiming Jobs with known-invalid config. For a Worker that claims durable
work, fail fast.

## Controlled process replacement vs in-process hot swap

Process replacement (start+verify new, drain old) costs orchestration and brief overlap capacity but never
breaks in-flight handlers; an in-process pointer swap is cheap but strands in-flight references on a closed
adapter. For Secret rotation, replace processes.

## Health-check at startup vs no external probe

A cheap bounded health endpoint can catch gross misconfiguration early but adds a dependency and still cannot
prove later generation success; skipping it keeps startup purely local. Either way, never send a **paid**
generation call to "test" the key.

---

# Hands-on Exercises

These map to the runnable artifact and its tests, which **were executed** (Python 3.10.12, fastapi 0.110.0,
httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 → **12 passed**; install via `requirements-day45.txt`) with a
**fake, no-network** Provider. The completion target is an **in-memory list, not PostgreSQL**; a real Provider
SDK/network, PostgreSQL, SQLAlchemy, Celery/Redis, Secret rotation/drain, and production are **NOT RUN**.

Run the tests:

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day45.txt
python3 -m py_compile day45_composition.py test_day45_composition.py
python3 -m pytest -q test_day45_composition.py
```

### Exercise 1: Assign process scope

Question: for 4 API processes (no Provider call) and 8 Worker processes (Provider call), how many Provider
clients exist, and what does each own?

Think First: which processes actually call the Provider?

Expected Output: 8 clients (one per Worker); each owns HTTP connections/pools, not database connections; API
processes create none.

Follow-up: if a future streaming API process calls the Provider, how many clients then?

### Exercise 2: Place the resource in the right scope

Question: classify Settings, the HTTP client, the Provider adapter, and `JobService` as app/process scope or
request/Job scope.

Expected Output: Settings/HTTP client/adapter = app/process (lifespan); `JobService` = per request/Job
(stateless).

Follow-up: why must a Job handler not close the shared client?

### Exercise 3: Design the Settings boundary

Question: write the validated `Settings` fields and say what `safe_log_fields()` returns.

Expected Output: `provider_api_key: SecretStr` (non-empty), `provider_base_url: AnyHttpUrl`, `provider_model`
(non-empty), `request_timeout_s` (0 < t ≤ 120); `safe_log_fields()` redacts the key.

Follow-up: why must the key never appear in a Job payload?

### Exercise 4: Fail-fast policy

Question: a Worker starts with an empty API key. What happens, and what must it not do?

Expected Output: `Settings.load()` raises `ValidationError`; the Worker stays not-ready and claims no Job; it
does not send a paid generation call to test the key.

Follow-up: does a green startup prove the Provider is reachable? (No — local validity ≠ external availability.)

### Exercise 5: Safe configuration-error log

Question: design the log fields for a config-validation failure.

Expected Output: `event=config_validation_failed`, `field`, stable `code`, component, settings version; never
the key, prompt, tenant data, or raw vendor output.

Follow-up: why not log the raw adapter/vendor error body?

### Exercise 6: Diagnose import-time construction

Question: a module builds `Settings` and an adapter at module scope. Name three failures and the fix.

Expected Output: tests fail during import before fakes inject; poor readiness classification; no close pairing.
Fix: construct in `create_app` + lifespan.

Follow-up: what may live at import time? (Types, routes, functions.)

### Exercise 7: Partial-initialization cleanup

Question: the HTTP client is created but adapter init fails. Write the assertions.

Expected Output: the already-created client is closed; no Container/readiness published; no Job claimed. Maps to
`test_partial_init_closes_client_and_no_readiness`.

Follow-up: why is "assert it raised" insufficient?

### Exercise 8: The Provider seam

Question: define the small `AIProvider` and say what the production adapter hides and translates.

Expected Output: `async generate(prompt, max_tokens) -> raw JSON`; the adapter hides SDK/HTTP/response
extraction and translates vendor errors to `ProviderTimeout`/`ProviderRateLimited`/`ProviderAuthentication`/
`ProviderTransport`.

Follow-up: where is the raw Provider JSON validated? (Worker Service, before completion, via Day44.)

### Exercise 9: First safe composition test

Question: design the first fake-runtime test.

Expected Output: fake Settings/Secret, tracking client, fake provider factory; enter `TestClient`, deterministic
call, exit; assert no network, fake used, client open inside then closed after, no Secret leak. Maps to
`test_fake_provider_injected_no_network_and_client_lifecycle`.

Follow-up: why configure overrides before entering `TestClient`?

### Exercise 10: Validation blocks completion

Question: a fake Provider returns invalid JSON. What must the use-site do?

Expected Output: `StructuredAIResult.model_validate_json` raises before completion; the completion list stays
empty. Maps to `test_invalid_provider_output_blocks_completion`.

Follow-up: why assert the empty completion list, not just the exception?

### Exercise 11: Rotation, drain, and rollback order

Question: sequence a Secret rotation and a graceful shutdown; then decide the interrupted-call recovery.

Expected Output: start+verify new Workers → drain old (stop new claims) → bounded in-flight window → close old →
verify; shutdown = stop intake → drain → close; interrupted call = no blind requeue, use correlation/idempotency/
audit. Never treat code rollback as DB rollback.

Follow-up: why keep old Workers if the new config is invalid?

---

# Relevant Framework Connections

## FastAPI

The lesson's runtime home: `create_app` as a Composition Root, an `asynccontextmanager` **lifespan** that owns
app-scoped resources, `Depends` that supplies them (request-local cache, not a cross-process singleton),
`Request.app.state` for the published `Container`, `dependency_overrides` for use-site substitution, and
`TestClient` whose context triggers lifespan startup/shutdown. A real HTTP runtime against a Provider is not
executed here (Day53); Day45 runs a fake, no-network composition.

## Pydantic v2

`Settings` as a validated, secret-aware boundary using `BaseModel`, `SecretStr`, `AnyHttpUrl`, `field_validator`,
`extra="forbid"`, and `frozen=True`; and the Day44 `StructuredAIResult.model_validate_json` reused to validate
raw Provider output **before** completion. Typed settings are a configuration boundary, not authorization or
encryption.

## HTTP client (httpx)

An async client/connection pool is process/app scoped and must be closed during lifespan shutdown. Day45 uses a
**tracking fake** client in tests to prove open-inside/closed-after and no network; a real `httpx.AsyncClient`
belongs to the production adapter's owning lifespan.

## PostgreSQL (future authority only)

Referenced only as the future durable authority. Day45 does **not** claim SQLAlchemy mapping, session
transactions, guarded durable completion, or DB runtime validation — Day46/47 own those. The completion target
here is an in-memory list.

---

# AI Backend Connections

## HTTP acceptance stays short; Providers belong to Workers

The multi-tenant AI Job API keeps HTTP acceptance short and pushes long Provider calls to Workers, each owning
its own app-scoped Provider client — the composition that makes the Day43 commit-before-202 shape operable.

## Provider output is untrusted even when transport succeeds

A successful HTTP response is not a valid result. The Worker validates the whole `StructuredAIResult` (Day44)
before any completion side effect, so an external model can never write a false `succeeded`.

## Adapters isolate vendor drift and enable deterministic tests

A small `AIProvider` seam with a production adapter and a `FakeAIProvider` isolates SDK/error drift and gives
no-network, no-cost test doubles — essential when the real dependency is a paid API.

## Secrets and cost discipline

API keys never travel in Job payloads, routine logs, public errors, or prompt/output traces; and interrupted
Provider calls are never blindly replayed, because token cost and duplicate paid calls are real. Recovery needs
correlation/idempotency evidence.

## Safe rotation and drain

New configuration is verified ready before old Workers drain; in-flight calls get a bounded, auditable recovery
window. This is how an AI backend rotates a Provider Secret without dropping or double-charging in-flight work.

---

# English Interview

## Key Vocabulary

Dependency injection, composition root, application lifespan, app/process scope vs request scope, `Depends`,
`dependency_overrides`, `TestClient`, `Settings`, `SecretStr`, fail-fast startup, readiness, adapter seam,
`AIProvider` protocol, vendor-error translation, graceful drain, Secret rotation, code rollback vs durable-fact
repair.

## Useful Expressions

"Resource ownership is per-process." · "Lifespan owns app-scoped resources; `Depends` supplies them." ·
"`SecretStr` hides display, it is not encryption." · "Fail fast, stay not-ready, don't claim Jobs." · "Verify
the new Workers ready before draining the old ones." · "Stop intake, drain, then close." · "Code rollback is not
database rollback."

## Beginner Question — What is dependency injection in FastAPI, and why should a shared Provider client be created in the application lifespan instead of inside a route?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "Dependency injection means a component receives its dependencies rather than constructing them directly,
> which makes the code testable and replaceable. A shared Provider client owns long-lived HTTP connection-pool
> resources, so it should be created once in the application lifespan at startup and closed once at shutdown.
> Creating it inside a route would rebuild the client on every request, cause connection churn, leak Secret
> handling into HTTP code, and give no controlled shutdown. `Depends` then supplies that already-created client
> to the route."

Assessment: an honest "不知道"; the taught answer covers receive-not-construct, the pooled-resource lifetime, and
why the route is the wrong place.

## Intermediate Question — A Provider API key is missing in a new deployment. What should happen during Worker startup, and how would you roll out the corrected configuration safely?

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "The Worker should fail fast: `Settings` validation raises, the Worker stays not ready, and it does not claim
> any Jobs. I would log a safe, allowlisted config-validation event with a stable code and settings version, no
> Secret. To roll out the fix, I start new Workers with the corrected configuration, require them to reach
> readiness, and only then drain the old Workers. If the new configuration is still invalid, I keep the old
> healthy Workers running and roll back the code/config. Rolling back configuration is not a database rollback —
> durable facts are unaffected."

Assessment: an honest "不知道"; the taught answer covers fail-fast, safe logging, verify-new-before-drain-old,
and the code-vs-DB rollback boundary.

## Senior Question — A new Provider Adapter release returns invalid JSON. Day44 validation blocks completion, but several Jobs have already called the Provider. Explain how you would contain the incident, recover safely, and prevent recurrence.

Student answer (verbatim):

> "不知道"

Strong spoken answer taught:

> "First I contain: stop the affected release from claiming new Jobs and route execution to a known-good
> version while keeping correct drain behavior. I preserve evidence — release version, settings version but
> never the Secret, provider and model, job/attempt/request/trace IDs, error category, and secure references to
> the original output. I roll back the application code/config and deploy a healthy Worker first, without
> claiming any database history was rolled back. I classify the affected Jobs by release window, attempt
> records, and output shape, remembering that validation blocking completion does not prove the external call
> never happened. Then I recover only through an idempotent, guarded, audited process after checking Provider
> correlation and idempotency evidence, reconciling Job, Attempt, Event, and Artifact records. I never blindly
> requeue or replay paid calls, mark invalid JSON succeeded, delete audit evidence, or fabricate a result.
> Finally I add negative regression tests and use a staged rollout to prevent recurrence."

Assessment: an honest "不知道"; the taught answer is the full contain → preserve → roll back → classify → guarded
audited recovery → reconcile → regression/staged-rollout arc.

## Common Weak Answer

"Just create the Provider client in the route with `Depends`, read the API key from the environment, and mock
the network in tests."

## Strong Answer

"Ownership is per-process: the lifespan creates the Provider client once and closes it at shutdown, `Depends`
supplies it, and `JobService` is stateless per request. The API key comes from validated, secret-aware
`Settings`, never a route or a Job payload. Tests compose `create_app` with a fake Settings and a fake Provider
factory and configure dependency overrides before entering `TestClient`, asserting the effect — client closed,
no network, empty completion on invalid output. Startup fails fast on invalid config, rotation verifies new
Workers before draining old ones, and code rollback is not a database rollback."

---

# Mental Model Summary

```text
1.  Composition boundary = the ONE place infrastructure is created and closed.
2.  Ownership is per-process; only processes that call the Provider create a client (8 Workers = 8 clients).
3.  A Provider client owns HTTP connections/pools, NOT database connections (DB is Day47).
4.  Lifespan owns app/process-scoped resources (Settings, HTTP client, ProviderAdapter); JobService is per request/Job.
5.  Depends() SUPPLIES an already-created dependency; its cache is request-local, NOT a cross-process singleton.
6.  get_provider returns the lifespan-created AIProvider; a yield dependency fits request scope (Day47 AsyncSession).
7.  Settings is the validated secret boundary; SecretStr hides display, is NOT encryption; keys never in payloads/logs.
8.  Fail fast on invalid LOCAL config -> not ready -> no claim; local validity != external Provider availability.
9.  Never send a PAID generation call on startup to test a key; a bounded health check can't prove later success.
10. Import time declares types/routes only; create_app + lifespan construct; publish Container only after full init.
11. Partial init -> close the already-created client, publish NO Container/readiness, claim NO Job (reverse-order close).
12. AIProvider is a SMALL seam; adapter translates vendor errors to stable types; Fake gives no-network/no-cost tests.
13. Worker validates raw Provider JSON via Day44 BEFORE completion; Router validates client input, not Provider results.
14. Test composition: create_app + fake factory + dependency_overrides BEFORE TestClient; test the EFFECT, clear overrides.
15. Rotation: start+verify NEW -> drain OLD -> bounded window -> close OLD; never drain healthy old before new is ready.
16. Shutdown order: stop new claims -> drain in-flight -> close client (never close first); no blind requeue of paid calls.
17. Code/config rollback protects FUTURE executions; interrupted calls + committed facts need audited, idempotent repair.

Starting model -> reasoning -> correction -> final model:
Initial: "the Worker owns it" (one global client); Provider client conflated with DB connections; unsure how
Depends/lifespan differ; SecretStr thought to mean non-plaintext security; partial init only needs "cancel the
client"; rollout might drain old before new is ready; in-process hot swap framed as a rollout-capacity issue;
first fake-runtime test and the three interview answers were "不知道".
Reasoning: pushed long Provider work to a Worker, chose per-request stateless services, kept the shared client
lifespan-scoped, chose an interface + fake for no-cost tests, refused a paid startup call and a blind requeue,
and gave the correct drain/close ordering.
Correction: per-process ownership (only Provider-calling processes create clients); HTTP pool vs DB scope;
lifespan owns / Depends supplies; SecretStr hides display only; partial init closes the created client and
publishes nothing; verify new before draining old; immutable per-process config with drain/restart replacement;
validate Provider output before completion and assert the empty completion list.
Final: composition boundary owns and closes app-scoped resources; Depends supplies interfaces; stateless services
per Job; Provider output untrusted until Day44 validation immediately before guarded completion; code/config
rollback protects the future while interrupted calls and durable facts need separate correlated, idempotent,
audited recovery.
```

---

# Today's Takeaway

Day45 is the composition boundary that makes Day44's typed contracts runnable without letting Routers or
business services own infrastructure. Settings are validated, secret-aware input to a process; the lifespan
creates and closes application-scoped resources; `Depends` supplies already-created interfaces; stateless
services are per request/Job. Each Worker process owns its own Provider client and drains before shutdown.
Provider output remains untrusted until Day44 validation succeeds immediately before a future guarded
completion. A release/config rollback protects future executions, while already-started Provider calls and
durable facts require separate, correlated, idempotent, audited recovery.

Most important mental model: the composition boundary — lifespan owns and closes app-scoped resources, `Depends`
supplies them, services stay stateless. Most important production risk: a Router that builds a Provider client
per request and reads the key from the environment (churn, Secret leak, no fakes, no drain). Most important
trade-off: a lifespan-owned resource + interface seam vs per-request construction + direct SDK. Most important
connection: Day53 implements a real OpenAI-compatible SDK behind this `AIProvider` seam. Most important
interview answer: ownership is per-process, the lifespan owns the client, and `Depends` supplies it.

Validation status: a minimal FastAPI composition/lifespan and **12 pytest cases** are **real executed local
runtime evidence** — executed here on Python 3.10.12 / fastapi 0.110.0 / httpx 0.27.0 / pydantic 2.5.0 / pytest
7.4.3 (pinned in `requirements-day45.txt`) → **12 passed** — but with a **fake, no-network** Provider and an
**in-memory** completion list, **not** PostgreSQL. A real Provider SDK/network/authentication, PostgreSQL/
SQLAlchemy transactions and durable completion, Celery/Redis Worker behavior, and deployment/Secret rotation/
drain/production are **NOT RUN**.

---

# Before Next Lesson Checklist

```markdown
- [ ] Can I explain why resource ownership is per-process, and how many Provider clients 8 Workers hold?
- [ ] Can I place Settings, the HTTP client, and the adapter in the lifespan, and keep JobService per request?
- [ ] Can I explain why `Depends()` supplies an instance and does not create a cross-process singleton?
- [ ] Can I design a validated, secret-aware `Settings` and say why `SecretStr` is not encryption?
- [ ] Can I justify fail-fast startup and explain why startup must not send a paid generation call?
- [ ] Can I design a safe, allowlisted configuration-error log?
- [ ] Can I diagnose import-time construction and move it into `create_app` + lifespan?
- [ ] Can I design partial-init cleanup that closes the client, publishes no readiness, and claims no Job?
- [ ] Can I define the small `AIProvider` seam and translate vendor errors to stable types?
- [ ] Can I write a composition test with a fake factory + dependency overrides before `TestClient`, testing the effect?
- [ ] Can I run the artifact tests (`pytest -q test_day45_composition.py`) and read the 12-passed evidence honestly?
- [ ] Can I sequence Secret rotation and graceful drain, and recover an interrupted call without blind requeue?
```

Preparation for Day46 (SQLAlchemy 2.0 Mapping for the Day42 Data Model): review this composition boundary, then
preview how the Day42 durable Job/Attempt/Event/Outbox/Upload-Session/Artifact model is mapped with SQLAlchemy
**without** merging ORM models with public Pydantic models — using the dependency boundary established here.
Day47 adds request-scoped `AsyncSession`/transaction/unit-of-work (distinct from the app-scoped Provider), and a
real Provider SDK (Day53) remains a later boundary.

---

Engineering Artifact: [projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md](../../projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md) · Code: [`day45_composition.py`](../../projects/ai-backend-data-layer/api/day45_composition.py) · Tests: [`test_day45_composition.py`](../../projects/ai-backend-data-layer/api/test_day45_composition.py)
