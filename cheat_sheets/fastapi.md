# FastAPI Cheat Sheet

## Purpose

One-page FastAPI review sheet for AI Backend Engineer preparation.

Focused on layered architecture, dependency injection, and production concurrency.

---

## Layered Architecture

```text
Request
   |
   v
Router      -> validate request model, delegate
   |
   v
Depends()   -> inject Service and its dependencies
   |
   v
Service     -> orchestrate workflow (stateless)
   |
   v
Browser / LLM  -> infrastructure behind interfaces
   |
   v
Repository  -> database abstraction
   |
   v
Database
   |
   v
Response    -> shaped by the response model
```

---

## Thin Router

```python
from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    request: SummarizeRequest,
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    return await service.summarize(request.url)
```

- Validate input with a request model.
- Shape output with a response model.
- Delegate to a service; no business logic here.
- `main.py` only creates the app, includes routers, and configures dependencies.

---

## Request and Response Models

```python
from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    url: str


class SummaryResponse(BaseModel):
    summary: str
    task_id: int
```

- Request model validates and documents input.
- Response model controls exactly what is returned.

---

## Dependency Injection with Depends()

```python
def get_summary_service(
    browser: BrowserClient = Depends(get_browser_client),
    llm: LLMClient = Depends(get_llm_client),
    repo: TaskRepository = Depends(get_task_repository),
) -> SummaryService:
    return SummaryService(browser=browser, llm=llm, repo=repo)
```

- `Depends()` is request-scoped dependency injection.
- Inject services; never construct them inside routes.
- Enables fakes in tests and provider swaps in production.

---

## Async Endpoints and Blocking Work

```python
@app.get("/report")
async def report():
    data = await asyncio.to_thread(build_report)   # blocking work off the loop
    return data
```

- Each request is a Task on the Event Loop.
- Never call blocking functions directly in `async def`.
- Use `asyncio.to_thread()` for unavoidable blocking work.
- Client disconnect can cancel the request Task.

---

## Long Jobs: Task Status Pattern

```text
POST /summarize -> return task_id immediately
GET  /tasks/{id} -> return task status/result
Worker -> pulls the job, runs the service, updates status
```

- Do not hold a connection for a 30-second LLM job.
- Queue + worker + status keeps the API responsive.

---

## Production Concurrency

```python
sem = asyncio.Semaphore(10)

async def call(url):
    async with sem:
        for attempt in range(5):
            try:
                return await service.summarize(url)
            except RateLimitError:
                await asyncio.sleep(2 ** attempt)
        raise
```

- Semaphore bounds concurrency to downstream capacity.
- Retry with exponential backoff on HTTP 429.
- Optimize for stable throughput, not maximum concurrency.

---

## Best Practices

- Keep routers thin; put logic in stateless services.
- Depend on interfaces; inject dependencies.
- Hide the database behind a repository.
- Return data from infrastructure layers, not framework models.
- Bound concurrency and handle rate limits explicitly.
- Scale horizontally with stateless services behind a queue.

---

## Common Mistakes

| Mistake | Risk |
|---------|------|
| Fat router with business logic | Untestable, duplicated logic |
| Constructing services inside routes | No injection, hard to test |
| Service knowing HTTP or SQL | Tight coupling, no reuse |
| Blocking call in `async def` | Freezes the Event Loop |
| Holding the connection for long jobs | Timeouts, connection pile-up |
| Unbounded concurrency to a provider | HTTP 429, pool exhaustion |

---

## Day43 AI Job API Contract and Request Lifecycle

Central rule:

```text
An HTTP response is a PROMISE about COMMITTED business state (not a report of an attempt).
Return 202 ONLY after ONE PostgreSQL tx commits Job + (tenant_id, idempotency_key) UNIQUE + Outbox intent.
```

### Status / error matrix

```text
202 Accepted = durable ASYNC commitment exists (NOT completion) -> body: job_id + stable status_url
201 Created  = created synchronously (NOT a redirect; 3xx is redirect)
200 OK       = GET a found Job -> current business status (queued/running/...) in body
4xx          = client-contract failure (bad/expired/unauthorized upload) -> NO Job, NO Outbox
409 Conflict = same tenant + same idempotency key + DIFFERENT logical input (never return the old Job as new)
5xx          = dependency cannot verify / PostgreSQL lookup/commit fails -> NEVER fake 404 or 202
expensive POST /jobs without Idempotency-Key -> reject (no unbounded duplicate acceptance)
DB lookup TIMEOUT after route match = 5xx (a completed miss is 404; an unfinished lookup is 5xx)
```

### Idempotency (lost-response safe)

```text
same tenant + same stable key + same input -> atomic FIND-OR-RETURN the original Job (same job_id + status_url)
  -> NO second Job, NO second Outbox intent
authority = (tenant_id, idempotency_key) UNIQUE + atomic create-or-return   (NOT SELECT-then-INSERT, which races)
bind the key to REQUEST MEANING; API idempotency != Provider idempotency
```

### Routing / tenant read

```text
router resolves method+path BEFORE handler/DB: 404 = no route, 405 = path exists but method unsupported
declare STATIC before DYNAMIC: /jobs/health before /jobs/{job_id} (or a global /health); validation can't fix routing
GET reads COMMITTED truth: WHERE tenant_id = trusted_authenticated_tenant AND job_id = :path_job_id
cross-tenant / no match -> 404 (NOT 403) -> no existence oracle; a UUID is NOT authorization
allowlist public fields: NEVER expose lease/fencing/Provider-metadata/Object-Storage-key/Outbox/Attempt internals
```

### Lifecycle / duplicate / cancel

```text
HTTP lifecycle (short) != durable background lifecycle (Relay -> Worker claim -> Provider -> guarded completion)
do NOT wait for an 8-min Provider call; an in-process BackgroundTask is NOT a durable Worker (deploy/crash loses it; Day55)
Relay scans published_at IS NULL; crash after publish before checkpoint -> expected at-least-once DUPLICATE
FIRST duplicate gate = guarded queued->running: 1 row winner may create Attempt/Event + call Provider; 0 rows -> STOP
  (lease/fencing protects stale COMPLETION later, not the first gate)
Artifact existence != success; cancel via POST /jobs/{id}/cancel (durable audited INTENT; semantics = "cancel requested, terminal outcome pending", not a resource DELETE)
cancel requested != cancellation completed (a Provider call may be in flight; terminal mechanics = Day54)
rollback a pre-COMMIT-202 release: roll back the CODE + reconcile committed facts; an idempotent 202 for the SAME Job is fine
```

### Weak vs strong (Day43)

```text
Weak:   "Return 202 right away."
Strong: "Return 202 only after the Job + Outbox transaction COMMITS; the response is a promise about committed state."

Weak:   "Same key, different input -> return the old Job."
Strong: "That's a 409 Conflict; never misrepresent the old Job as a new intent."

Weak:   "A DB timeout means the Job wasn't found -> 404."
Strong: "A completed miss is 404; a lookup that can't finish is 5xx. Never fake 404/202 on a dependency outage."

Weak:   "Another tenant's id -> 403 so they know it's not theirs."
Strong: "Return 404 filtered by tenant + job_id; the API must not be an existence oracle."

Weak:   "Duplicate dispatch is handled by lease/fencing."
Strong: "The first gate is the guarded queued->running (1 row winner / 0 rows stop); fencing protects completion later."
```

### One-line mental model

```text
The API is an honest promise over the Day42 durable contract: 202 after commit, retries converge via the unique
constraint, precise status codes, routing before logic, tenant-isolated reads (no oracle), durable background work.
```

Validation: CONCEPTUAL / STATIC CONTRACT REVIEW only — FastAPI / PostgreSQL / Relay-Worker / Redis-Object-Storage-
Provider / integration / production runtime NOT RUN. Pydantic v2 (Day44), DI/lifespan/adapters (Day45),
SQLAlchemy/Alembic (Day46-48), durable cancellation (Day54), Celery (Day55) are future boundaries.

Related: [Day43 lesson](../docs/fastapi/day43-ai-backend-product-contract-and-fastapi-request-lifecycle.md) · [Day43 API contract](../projects/ai-backend-data-layer/api/day43-ai-job-api-contract.md)

---

## Day44 Pydantic v2 and Structured AI Input/Output Contracts

Central rule:

```text
Boundary ladder: JSON-valid -> Pydantic-valid structure -> authenticated -> authorized -> app invariants
                 -> PostgreSQL constraint + atomic tx -> committed durable truth.
Pydantic proves ONE rung (declared structure); NOT authorization, NOT a durable commit.
```

### Request models

```text
tenant_id is TRUSTED AUTH CONTEXT, NOT a request-body field (a body tenant_id = cross-tenant authz risk)
job_status is server-owned; extra="forbid" rejects it + tenant_id + unexpected_debug (don't silently ignore)
max_tokens: allowed only if the product supports it -> strict int + bounded; else reject entirely
JobRequest = discriminated union on task_type: SummarizeRequest (forbids output_schema) | ExtractStructuredRequest (requires non-empty output_schema)
UNIQUE (tenant_id, idempotency_key) + the tx stay the concurrency/commit authority (Pydantic can't see DB ownership)
```

### Strict types / Provider output

```text
MaxTokens = Annotated[int, Field(strict=True, ge=1, le=200000)]   # "2000" NOT coerced (billing/audit)
Confidence = Annotated[float, Field(strict=True, ge=0, le=1)]     # "very sure" rejected
NO global strictness (JSON represents UUIDs/timestamps as strings); conversions -> explicit tested adapter
Provider output = FULLY untrusted input -> StructuredAIResult (extra="forbid", NO Provider job_status)
  Pydantic validates citation/URL SHAPE; it does NOT prove citations are true/grounded (shape != grounding)
```

### Responses / error envelope

```text
persistence != internal != public API representation; allowlist the public response (job_id + job_status minimal)
JobStatusResponse = discriminated union on job_status:
  queued/running -> NO result, NO failure | succeeded -> result REQUIRED | failed -> failure REQUIRED
a failed Job is a successfully READ resource -> HTTP 200 + business status "failed"
PublicErrorResponse.error = {code (stable machine), message (safe text), field_errors?, request_id?}
  HTTP status = error CLASS; never leak SQL/tracebacks/credentials/raw Provider errors/raw keys/cross-tenant existence
```

### Entry points / gate / incident

```text
model_validate(obj) / model_validate_json(raw) -> validate UNTRUSTED input
model_dump(model) -> serialize an ALREADY-validated model
model_construct(...) -> SKIPS validation/validators/nested conversion/extra="forbid" -> NEVER on untrusted input
TypeAdapter(Union[...]) -> validate a discriminated union
validate BEFORE side effects: validate_provider_output_before_completion raises before on_completion runs
  negative test asserts BOTH a ValidationError AND completion_calls == [] (test the effect, not just the signal)
model_construct() incident (37 Jobs falsely succeeded): disable path + route away -> preserve evidence ->
  roll back the CODE (restore model_validate) -> add negative regression test -> classify by release/attempt/output
  -> idempotent guarded AUDITED repair -> reconcile Job/Attempt/Event/Artifact; code rollback != DB rollback
```

### Weak vs strong (Day44)

```text
Weak:   "Accept tenant_id from the body."
Strong: "tenant_id is trusted auth context; a body tenant_id is a cross-tenant authz risk. Pydantic validates intent, not identity."

Weak:   "The model validated, so the request is authorized and safe to commit."
Strong: "Pydantic proves structure only; authorization and the DB constraint + tx are separate boundaries."

Weak:   "Use model_construct() for speed on Provider output."
Strong: "model_construct skips validation; untrusted input uses model_validate/model_validate_json."

Weak:   "The negative test asserts a ValidationError."
Strong: "It also asserts the completion callback never ran; a bad impl could complete before validating."

Weak:   "Roll back the release and the bad Jobs are fixed."
Strong: "Code rollback protects future traffic; committed facts need an idempotent audited repair. Code rollback != DB rollback."
```

### One-line mental model

```text
Pydantic makes the Day43 contract executable but earns ONE guarantee (structure): keep JSON-valid/Pydantic-valid/
authenticated/authorized/committed separate, validate Provider output before side effects, never model_construct untrusted.
```

Validation: REAL Pydantic v2 tests executed (Pydantic 2.5.0, pytest -> 11 passed; completion target is an
in-memory callback, not PostgreSQL). FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/integration/production
NOT RUN. DI/lifespan/adapters = Day45; SQLAlchemy = Day46; real Provider SDK = Day53.

Related: [Day44 lesson](../docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md) · [Day44 contracts design](../projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md) · [code](../projects/ai-backend-data-layer/api/day44_pydantic_contracts.py) · [tests](../projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py)
