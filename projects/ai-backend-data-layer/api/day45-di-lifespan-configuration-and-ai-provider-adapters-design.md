# Day45 — Dependency Injection, Lifespan, Configuration and AI Provider Adapters (Design)

Executable composition design for the Day44 typed contracts. This turns the Day44
request/response/Provider models into a runnable FastAPI/Worker composition where
**Routers and business services never own infrastructure**. Runnable code:
[`day45_composition.py`](day45_composition.py); executed tests:
[`test_day45_composition.py`](test_day45_composition.py); pinned deps:
[`requirements-day45.txt`](requirements-day45.txt).

> Scope honesty: this is a MINIMAL local composition executed with FastAPI's
> `TestClient` and a FAKE, no-network Provider. A real Provider SDK/network,
> PostgreSQL, SQLAlchemy/Alembic, Celery/Redis/Object Storage, Secret rotation/
> drain, and production are **NOT RUN** (Day46/47/50/53/54/55/56). The completion
> target is an in-memory list on `app.state`, **not** a PostgreSQL guarded commit.

---

## 1. Ownership: per-process, not "the Worker owns everything"

```text
Resource ownership is PER PROCESS.
- An API process that never calls the Provider should NOT create a Provider client.
- A Worker process that calls the Provider creates and closes its OWN client in ITS lifespan.
- A future sync/streaming API process that calls the Provider owns a SEPARATE client too.
- 8 Worker processes = 8 independent app-scoped clients (separate memory; no cross-process global).
A Provider client normally owns HTTP connections/pools, NOT database connections (DB pool/session is Day47).
```

Long (e.g. eight-minute) Provider execution belongs to a **Worker**, not an HTTP
Router — but "Worker owns it" is not "one global client." Every process owns the
resources it actually uses.

---

## 2. Dependency injection and scopes

```text
Lifespan (app/process scope)  ->  owns expensive closeable resources: Settings, HTTP client, ProviderAdapter.
Depends()                     ->  SUPPLIES an already-created dependency; it does NOT create a singleton.
                                  Default FastAPI dependency cache is WITHIN one request graph, not across
                                  requests or processes.
get_provider                  ->  returns the lifespan-created AIProvider (does not build a new adapter per call).
JobService                    ->  stateless, lightweight, per request/Job; carries no tenant/trace/job state.
yield dependency              ->  fits a REQUEST-scoped resource (Day47 AsyncSession), NOT closing a shared
                                  app-scoped adapter at every request end.
```

Router/handler code must not construct `OpenAICompatibleAdapter` or read API keys.

---

## 3. Settings and secrets boundary

```text
Settings (Pydantic v2, extra="forbid", frozen): provider_api_key: SecretStr (non-empty),
  provider_base_url: AnyHttpUrl, provider_model: str(min_length=1), request_timeout_s: float (0 < t <= 120),
  + allowlisted non-sensitive labels provider_name / settings_version (defaulted).
Settings.load(env) -> fail-fast: missing/invalid -> ValidationError at startup -> Worker stays NOT ready, no claim.
safe_log_fields()  -> emits ONLY allowlisted non-sensitive fields: provider_name, provider_model,
  request_timeout_s, settings_version, provider_api_key=***REDACTED***. NEVER the key, whole Settings,
  raw model_dump(), or provider_base_url (which can carry userinfo / internal host / port / private endpoint path).
```

- API key comes from validated **Settings**, never Router code and never Job
  payloads (payloads are persisted/replayed/logged).
- Do **not** send a paid generation call on startup to "test the key." A cheap,
  bounded, no-side-effect health endpoint may be a separately designed check if
  available; it still cannot prove later generation success.
- `SecretStr` reduces accidental print/repr/serialization exposure. It is **not**
  memory encryption and does not stop a deliberate `get_secret_value()` log,
  permission mistakes, or bad Secret-store security.
- Local Settings validation proves the **local config** is well-formed; it does
  **not** prove the external Provider is reachable/authenticated right now.

---

## 4. Lifespan startup, shutdown, and partial initialization

```text
Import time            -> declare types/routes/functions ONLY. No Settings/client/adapter at module scope.
create_app(settings,   -> receives Settings + explicit factories (http_client_factory, provider_factory).
  *, factories)
Lifespan order         -> Settings(validated) -> async HTTP client -> ProviderAdapter -> publish Container
                          -> yield ready -> clear container -> close resources (REVERSE creation order).
Partial init           -> if the adapter factory raises AFTER the client is created: close the client,
                          publish NO Container/Provider, startup FAILS, Worker does not claim a Job.
```

Module-level construction breaks tests during import (before fakes can be
injected), gives poor readiness classification, and has no dependable close
pairing. Reverse-order release is expressed with `asynccontextmanager` +
`try/finally` (or `AsyncExitStack`).

---

## 5. AI Provider Adapter seam

```text
AIProvider (Protocol): async generate(prompt, max_tokens) -> RAW untrusted JSON text.
OpenAICompatibleAdapter: production shape; hides SDK init/request/response extraction + HTTP ownership.
  Translates faults over an INJECTED transport callable (no real network) to stable errors:
  builtin/asyncio timeout -> ProviderTimeout; status 429 -> ProviderRateLimited; 401/403 -> ProviderAuthentication;
  ConnectionError/other -> ProviderTransport. With NO transport injected it raises NotImplementedError.
  The real OpenAI-compatible SDK call + response parsing are Day53 (NOT run in Day45).
FakeAIProvider: deterministic valid/invalid JSON or a deterministic classified error; no network, no cost.
Worker Service: validates raw JSON via Day44 StructuredAIResult.model_validate_json(...) BEFORE completion.
```

Keep the interface **small**: do not leak a whole vendor SDK's types/params into
services. The Adapter may normalize transport detail; it does **not** own the Job
lifecycle. Day56 (not this lesson) owns retry/backoff/cost/backpressure policy.

---

## 6. Testing composition and validation boundaries

```text
create_app(test_settings, http_client_factory, provider_factory) -> no real client during lifespan startup.
FastAPI dependency_overrides -> use-site substitution of get_provider; configure BEFORE entering TestClient
  (its context triggers lifespan startup); an override alone does NOT stop a lifespan from creating a real
  resource; clear overrides after tests.
First safe test  -> fake Settings/Secret, tracking HTTP client (records close), fake adapter/provider factory;
  enter TestClient, call the SHORT route (GET /provider/status, resolves the Provider via Depends but does NOT
  run it), exit; assert: no network, resource OPEN inside the context, CLOSED after exit, provider.calls==0 (the
  HTTP path never runs the Provider), and no Secret in result/log assertions. The Provider call itself runs in a
  worker-style harness (WorkerJobRunner), not a route.
Partial-init test -> tracking client created; provider factory raises; assert startup raises, client closed,
  Container not published, no Worker claim.
Worker harness -> the (possibly long) Provider call + Day44 validation + completion run in WorkerJobRunner,
  NOT in an HTTP route; the HTTP route only resolves the Provider via Depends (short boundary).
Reuse Day44 -> test the EFFECT (empty completion list), not only the exception.
```

Executed tests in `test_day45_composition.py` (19 cases):

```text
1  short HTTP route resolves the Provider via Depends WITHOUT running it (client open->closed, no network, provider.calls==0)
2  worker harness: valid Provider output reaches the completion list exactly once
3  worker harness: invalid raw Provider output CANNOT reach completion (raises + empty completion list)
4  partial adapter init closes the already-created client, publishes no Container/readiness
5  get_provider raises ProviderNotReady before the Container is published
6  Settings fail-fast: missing API key -> ValidationError
7  Settings reject empty API key
8  Settings reject non-positive timeout
9  Secret not rendered in repr/str/safe_log_fields (but get_secret_value still works deliberately)
10 safe_log_fields excludes sensitive base-URL parts (userinfo/internal host/port/private path); only allowlisted fields
11 Secret does not leak into the short HTTP route response body
12 dependency override applied BEFORE TestClient, then cleared -> original lifespan wiring restored in a fresh lifecycle
13 JobService is stateless and per-Job (only the injected interface, no cross-Job state)
14 adapter translates a timeout -> ProviderTimeout (injected transport)
15 adapter translates an HTTP-429-style error -> ProviderRateLimited
16 adapter translates an HTTP-401/403-style error -> ProviderAuthentication
17 adapter translates a connection/other fault -> ProviderTransport
18 adapter without an injected transport raises NotImplementedError (no real SDK in Day45)
19 adapter passes a successful transport's raw JSON through unchanged (validated downstream by Day44)
```

---

## 7. Configuration rotation, graceful drain, and rollback

```text
Immutable per-process config -> do NOT hot-swap app.state.provider and immediately close the old adapter:
  in-flight handlers still hold the old reference; newer handlers use the new one.
Secret rotation via controlled process replacement:
  1) start new Workers with new config; 2) require successful local startup/readiness;
  3) THEN drain old Workers (stop claiming new Jobs); 4) bounded drain window for in-flight Jobs;
  5) close old adapter/client + terminate old process; 6) verify no old settings version + healthy evidence.
Graceful shutdown order -> stop new claims FIRST, preserve evidence, handle in-flight under a bounded drain,
  THEN close the Provider client. Never close it first.
Rollback -> code/config only; deploy a healthy new Worker first; if new config is invalid, KEEP old Workers
  running and roll back/fix. Code/config rollback is NOT a PostgreSQL rollback.
Interrupted Provider call at drain deadline -> do NOT blindly requeue: the call may have run, cost money, or
  return later. Day34 lease/fencing, Day40 at-least-once, Day55 Worker recovery govern guarded/audited recovery.
```

---

## 8. Integrated invalid-Provider-output incident (conceptual)

```text
Scenario: a new adapter release starts normally and claims Jobs, but a vendor format change yields invalid JSON.
          Day44 validation blocks completion.
Contain : stop the affected release from claiming new Jobs; route to a known-good version; keep correct drain.
Preserve: release version, settings version (never the Secret), provider/model, job/attempt/request/trace IDs,
          error category, time window, secure references to original output/audit evidence.
Roll back: application code/config only; deploy the healthy Worker first; DB history is NOT rolled back.
Classify : by release/time/attempt/output. Validation-before-completion does NOT prove the external call never ran.
Recover : idempotent, guarded, AUDITED, only after correlation/idempotency evidence is checked; reconcile
          Job/Attempt/Event/Artifact.
Never   : blind requeue/replay of paid calls, mark raw invalid JSON succeeded, delete audit, fabricate an
          Artifact, or write Secret/prompt/raw output to routine logs.
```

---

## Run instructions

```text
cd projects/ai-backend-data-layer/api
python3 -m pip install -r requirements-day45.txt      # pydantic==2.5.0, pytest==7.4.3, fastapi==0.110.0, httpx==0.27.0
python3 -m py_compile day45_composition.py test_day45_composition.py
python3 -m pytest -q test_day45_composition.py
```

---

## Validation and evidence classification

```text
REAL RUNTIME (executed)  : a minimal FastAPI composition/lifespan + 19 pytest cases with a FAKE no-network
                           Provider. Executed here:
                             `python3 -m pip install -r requirements-day45.txt`
                             `python3 -m py_compile day45_composition.py test_day45_composition.py` passed;
                             `python3 -m pytest -q test_day45_composition.py` -> 19 passed.
                           Environment: Python 3.10.12, fastapi 0.110.0, httpx 0.27.0, pydantic 2.5.0,
                           pytest 7.4.3 (pinned in requirements-day45.txt).
IN-MEMORY ONLY           : the completion target is an in-memory list on app.state, NOT PostgreSQL.
NOT RUN                  : real Provider authentication/network/SDK compatibility; PostgreSQL/SQLAlchemy
                           transactions and durable completion; Celery/Redis Worker behavior; deployment,
                           Secret rotation, drain/recovery, or production validation.
BOUNDARY (unchanged)     : Pydantic/local-config validation != authentication != authorization != application
                           invariants != PostgreSQL commit. Local Settings validity != external Provider
                           availability. SecretStr != encryption. Code/config rollback != durable-fact repair.
```

---

Lesson: [`docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md`](../../../docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md)
· Day44 contract reused: [`day44_pydantic_contracts.py`](day44_pydantic_contracts.py)
