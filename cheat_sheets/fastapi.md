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
MaxTokens = Annotated[StrictInt, Field(ge=1, le=8_000)]  # REQUIRED; "2000" NOT coerced; 8001 out of range (billing/audit)
Confidence = Annotated[float, Field(strict=True, ge=0, le=1)]     # "very sure" rejected
OutputSchema = dict[str, Literal["string","number","boolean"]] (Field min_length=1): {"company":1} / {"company":"integer"} rejected; NOT a full JSON Schema engine
upload_session_id : UUID and public job_id : UUID (Day31 model) -> "u1"/"j1" rejected at the boundary
Citation.url : AnyHttpUrl (scheme + host) -> a bare "https://" rejected; URL shape != source authz != SSRF != grounding
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

Validation: REAL Pydantic v2 tests executed (Pydantic 2.5.0, pytest 7.4.3 -> 37 passed; deps pinned in
`projects/ai-backend-data-layer/api/requirements.txt`; completion target is an in-memory callback, not
PostgreSQL). FastAPI/auth/PostgreSQL/SQLAlchemy/real-Provider/integration/production NOT RUN. DI/lifespan/
adapters = Day45; SQLAlchemy = Day46; real Provider SDK = Day53.

Related: [Day44 lesson](../docs/fastapi/day44-pydantic-v2-and-structured-ai-input-output-contracts.md) · [Day44 contracts design](../projects/ai-backend-data-layer/api/day44-pydantic-contracts-design.md) · [code](../projects/ai-backend-data-layer/api/day44_pydantic_contracts.py) · [tests](../projects/ai-backend-data-layer/api/test_day44_pydantic_contracts.py)

---

## Day45 Dependency Injection, Lifespan, Configuration and AI Provider Adapters

Central rule:

```text
Composition boundary = the ONE place infrastructure is created and closed.
Lifespan OWNS app/process-scoped resources; Depends() SUPPLIES them; services are stateless per request/Job.
```

### Ownership + scopes

```text
Ownership is PER PROCESS: only processes that CALL the Provider create a client (8 Workers = 8 clients; separate memory)
Provider client owns HTTP connections/pools, NOT database connections (DB pool/session = Day47)
app/process scope: Settings, async HTTP client, ProviderAdapter (lifespan)   | request/Job scope: JobService (stateless)
Depends() supplies an ALREADY-created dependency; default cache is request-local, NOT a cross-process singleton
get_provider -> returns the lifespan-created AIProvider (not a new adapter per call)
yield dependency fits a REQUEST-scoped resource (Day47 AsyncSession), NOT closing a shared app-scoped adapter
```

### Settings / secrets

```text
Settings (Pydantic v2, extra="forbid", frozen): provider_api_key: SecretStr (non-empty), provider_base_url: AnyHttpUrl,
  provider_model: str(min_length=1), request_timeout_s: 0 < t <= 120, + allowlisted labels provider_name / settings_version
Settings.load(env) -> FAIL FAST: missing/invalid -> ValidationError at startup -> not ready, no claim
safe_log_fields() -> emits ONLY provider_name/model/timeout/settings_version + redacted key; NEVER the key, whole Settings,
  raw model_dump(), or provider_base_url (can carry userinfo/internal host/port/private endpoint path)
SecretStr reduces accidental display; it is NOT encryption and does NOT stop deliberate get_secret_value() logging
API key comes from validated Settings; NEVER Router code, NEVER a Job payload (payloads are persisted/replayed/logged)
local Settings validity != external Provider availability; do NOT send a PAID generation call on startup to test a key
```

### Lifespan / partial init / adapter seam

```text
import time -> declare types/routes ONLY (no Settings/client/adapter at module scope)
create_app(settings, *, http_client_factory, provider_factory) -> explicit composition root
lifespan order: Settings(validated) -> HTTP client -> ProviderAdapter -> PUBLISH Container -> yield -> clear -> close (REVERSE)
partial init (adapter factory raises after client created): CLOSE the client, publish NO Container/readiness, claim NO Job
AIProvider = small Protocol: async generate(prompt, max_tokens) -> RAW untrusted JSON
OpenAICompatibleAdapter translates faults over an INJECTED transport (no real network) -> ProviderTimeout(timeout)/RateLimited(429)/Authentication(401,403)/Transport(conn); asyncio.CancelledError PROPAGATES UNCHANGED (cooperative drain/shutdown, NOT a vendor fault); no transport -> NotImplementedError; real SDK = Day53
FakeAIProvider -> deterministic valid/invalid JSON or classified error (no network, no cost)
HTTP route stays SHORT (GET /provider/status only RESOLVES the Provider via Depends); the (possibly long) Provider call + Day44 validation + in-memory completion run in a worker-style harness (WorkerJobRunner), NOT a route
Worker Service validates raw JSON via Day44 StructuredAIResult.model_validate_json BEFORE completion (Router validates client input, not Provider results)
```

### Test composition / rotation / drain

```text
create_app(test_settings, fake_provider_factory) + dependency_overrides for get_provider, configured BEFORE TestClient
  (its context triggers lifespan startup; an override alone does NOT stop a lifespan creating a real resource); clear overrides after
first safe test: fake Settings/Secret + tracking client (records close) + fake factory -> enter, deterministic call, exit
  assert: no network, fake used, resource OPEN inside / CLOSED after, no Secret in result/log (test the EFFECT)
rotation: start+verify NEW Workers ready -> THEN drain OLD (stop new claims) -> bounded in-flight window -> close OLD -> verify
  never drain healthy OLD before NEW is ready; invalid new config -> keep OLD running, roll back
shutdown order: stop new claims -> drain in-flight -> close client (NEVER close first)
interrupted Provider call at drain deadline -> NO blind requeue (may have run/cost/return later); correlation+idempotency+audit
code/config rollback protects the FUTURE; committed facts + interrupted calls need an idempotent guarded AUDITED repair
```

### Weak vs strong (Day45)

```text
Weak:   "Create the Provider client in the route with Depends and read the key from env."
Strong: "The lifespan owns the client once; Depends supplies it; the key comes from validated Settings, never a route or payload."

Weak:   "Depends() gives an app-wide singleton."
Strong: "Depends supplies an already-created dependency; its cache is request-local. The lifespan owns the shared resource."

Weak:   "SecretStr means the key is safe."
Strong: "SecretStr hides accidental display only; it is not encryption and doesn't replace permissions/rotation/secure logging."

Weak:   "Partial init just needs to raise / cancel the client."
Strong: "Close the already-created client, publish no Container/readiness, and claim no Job."

Weak:   "Drain the old Workers, then roll out the new config."
Strong: "Verify new Workers ready first, then drain old; keep old running if the new config is invalid."
```

### One-line mental model

```text
Day45 composes Day44's contracts into a runnable FastAPI/Worker: lifespan owns/closes app-scoped resources, Depends supplies
interfaces, services are stateless, Provider output stays untrusted until Day44 validation; code rollback != durable-fact repair.
```

Validation: REAL local FastAPI composition tests executed with a FAKE no-network Provider (Python 3.10.12, fastapi 0.110.0,
httpx 0.27.0, pydantic 2.5.0, pytest 7.4.3 -> 20 passed; deps pinned in
`projects/ai-backend-data-layer/api/requirements-day45.txt`; completion target is an in-memory list, not PostgreSQL).
Real Provider SDK/network, PostgreSQL/SQLAlchemy, Celery/Redis, Secret rotation/drain, and production NOT RUN.
SQLAlchemy mapping = Day46; async sessions/tx = Day47; real Provider SDK = Day53.

Related: [Day45 lesson](../docs/fastapi/day45-dependency-injection-lifespan-configuration-and-ai-provider-adapters.md) · [Day45 composition design](../projects/ai-backend-data-layer/api/day45-di-lifespan-configuration-and-ai-provider-adapters-design.md) · [code](../projects/ai-backend-data-layer/api/day45_composition.py) · [tests](../projects/ai-backend-data-layer/api/test_day45_composition.py)

---

## Day46 SQLAlchemy 2.0 Mapping for the Day42 Data Model

Central rule:

```text
ORM mapping REPRESENTS the database contract; it does NOT silently REPLACE it.
Day46 MAPS it -> Day47 DRIVES it (sessions/tx/repo/UoW) -> Day48 EVOLVES it (Alembic).
```

### Typed declarative mapping

```text
class Base(DeclarativeBase): metadata = MetaData(schema="app")   # exact existing app-schema identity
Mapped[T] = mapped_column(...)   # Mapped[T] = ORM-managed typed attr; mapped_column = column metadata (plain annotation != mapping)
types match Day42 exactly: UUID(as_uuid=True), Text, Integer, BigInteger, Boolean, TIMESTAMP(timezone=True), JSONB
server-GENERATED values are SERVER defaults: server_default=text("gen_random_uuid()"/"now()"/"'queued'"/"0"/"false"/"'{}'::jsonb")
"metadata" column is reserved by Declarative -> map as event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, ...)
```

### Constraints / integrity (names preserved)

```text
Job: jobs_tenant_idempotency_unique UNIQUE(tenant_id, idempotency_key)  | jobs_tenant_id_unique UNIQUE(tenant_id, job_id)
     jobs_status_allowed CHECK (TEXT+CHECK, NOT native enum -> enum is Day48) | jobs_attempt_count_non_negative CHECK
     jobs_succeeded_has_finished_at CHECK(status<>'succeeded' OR finished_at IS NOT NULL)
     jobs_tenant_fk FK -> tenants ON DELETE RESTRICT
Mapped[datetime | None] + nullable=True ALLOW null; they do NOT enforce the CHECK (the CHECK does)
JobAttempt: UNIQUE(job_id, attempt_number) = retry ordinal JOB-scoped (NOT tenant, NOT global; Job B may reuse 1)
            UNIQUE(job_id, attempt_id) = candidate key for provenance
JobEvent: FK (job_id, attempt_id) -> job_attempts(job_id, attempt_id) = same-Job provenance; NULL attempt_id = Job-level event
ON DELETE RESTRICT everywhere; NO cascade/delete-orphan; relationship() = NAVIGATION only, NOT integrity
parent->child relationships set passive_deletes="all" -> ORM emits NO pre-delete UPDATE/DELETE (never NULLs a NOT NULL child FK); PostgreSQL ON DELETE RESTRICT is the FINAL delete decision (not a cascade; cascade stays save-update/merge)
```

### Boundaries / scope / evidence

```text
Pydantic public models != ORM persistence models (never merged/inherited; no tenant/audit/persistence leak)
neither Pydantic nor ORM classes PROVE PostgreSQL constraint behavior (that is PostgreSQL's job)
Outbox: PostgreSQL-owned dispatch INTENT; published_at NULL = checkpoint not recorded, NOT "never sent" (at-least-once)
ResultArtifact stores attempt_id ONLY (job ownership DERIVED via Attempt; no denormalized job_id without constraint)
UploadSession/ResultArtifact store Object Storage REFERENCES/metadata, never large bytes/signed URLs/credentials
Tenant = minimal support stub (preserve FKs/candidate keys); tenant_id stays an explicit mapped column/FK (NOT derived away)
Document + job_documents = stated unimplemented limitation (NOT a half-built relationship)
NO Engine/AsyncSession/transaction/UoW in Day46 (Day47: one Engine/process, one session/request-Job)
static metadata tests prove DECLARED structure; create_all() success != schema compatibility; real PostgreSQL runtime = separate
negative constraint test expects a REJECTED write (CHECK violation / IntegrityError), NOT an empty query result
```

### Weak vs strong (Day46)

```text
Weak:   "Defining ORM models makes the ORM the schema authority."
Strong: "In an existing system the ORM faithfully maps the contract; PostgreSQL stays authority; change is Day48 migration."

Weak:   "Mapped[datetime | None] enforces 'succeeded implies finished_at'."
Strong: "Nullability only allows NULL; the jobs_succeeded_has_finished_at CHECK enforces it, and a negative test expects a rejected write."

Weak:   "UNIQUE(tenant_id, attempt_id) scopes the Attempt."
Strong: "Retry ordinal is Job-scoped: UNIQUE(job_id, attempt_number); Job B may reuse Attempt 1."

Weak:   "cascade='all, delete-orphan' keeps children tidy."
Strong: "Day42 requires ON DELETE RESTRICT; audit/recovery evidence must not be erased; relationship() is navigation only."

Weak:   "create_all() succeeded, so the mapping matches the schema."
Strong: "Creation success isn't compatibility; static tests prove structure and a runtime test applies the Day42 SQL to prove behavior."
```

### One-line mental model

```text
Day46 maps the Day42 durable PostgreSQL contract into faithful SQLAlchemy 2.0 models (app schema, server defaults, named
UNIQUE/CHECK/FK, RESTRICT, TEXT+CHECK, composite provenance) without changing authority; Day47 drives it, Day48 evolves it.
```

Validation: REAL static metadata-contract tests executed (Python 3.10.12, SQLAlchemy 2.0.29, pytest 7.4.3 -> 20 passed;
deps pinned in `projects/ai-backend-data-layer/api/requirements-day46.txt`; declared STRUCTURE only). PostgreSQL runtime
NOT RUN (no server; create_all() not used and not compatibility evidence). Sessions/transactions = Day47; Alembic = Day48;
Celery/Provider/Object-Storage runtime, integration, production NOT RUN.

Related: [Day46 lesson](../docs/fastapi/day46-sqlalchemy-mapping-for-the-day42-data-model.md) · [Day46 mapping design](../projects/ai-backend-data-layer/api/day46-sqlalchemy-mapping-for-the-day42-data-model-design.md) · [code](../projects/ai-backend-data-layer/api/day46_orm_mapping.py) · [tests](../projects/ai-backend-data-layer/api/test_day46_orm_mapping.py)

---

## Day47 Async Sessions, Transactions, Repository and Unit of Work

Central rule:

```text
One process owns ONE Engine + a session factory. Each request/Job = a FRESH UoW (one isolated AsyncSession + repos).
The UoW runs ONE short EXPLICIT-commit transaction; the long/paid Provider call happens BETWEEN two short UoWs, never inside one.
```

### Scope / ownership

```text
AsyncEngine = PROCESS-scoped (one per process via lifespan/Worker startup; NOT one per deployment)
async_sessionmaker = PROCESS-scoped factory; creates a NEW AsyncSession on demand (NOT a shared batch of live Sessions)
AsyncSession = request/Job-scoped; identity-map + pending + tx state; NEVER global/shared (concurrent Jobs pollute each other)
one UoW = one Session + repositories; the FACTORY is shared, not the Session
```

### Repository / UoW / lifecycle

```text
Repository -> receives the UoW-injected Session; expresses DB ops; NEVER creates Engine/Session, NEVER commit/close
UnitOfWork -> owns ONE Session, exposes repos, EXPLICIT await uow.commit() (no auto-commit), rollback on exception/uncommitted exit, ALWAYS close
close() ends the Session + returns the connection to the pool; it is NOT a rollback and does NOT dispose the Engine
flush != commit: flush executes SQL in the CURRENT tx (server ids usable for a dependent write) but is NOT durable/cross-session visible
IntegrityError = PostgreSQL rejected an illegal write and ABORTED the tx (integrity protected, not broken) -> must rollback before reuse
commit exception = UNKNOWN outcome (DB may have committed before the response was lost) -> rollback/close, reload by stable id via a NEW Session, do NOT replay
```

### Guarded claim / completion / Provider boundary

```text
guarded claim = single UPDATE app.jobs SET job_status='running' WHERE job_id=:id AND tenant_id=:tenant_id AND job_status='queued' RETURNING job_id (NOT SELECT-then-UPDATE)
EVERY guarded app.jobs mutation (claim/complete/fail) binds tenant_id as a REQUIRED durable ownership predicate (Day42/Day46; trusted context, NOT derived from job_id; a job_id alone is not authz). Wrong tenant -> 0 rows. NOT Day52 auth.
  1 row = claimed | 0 rows = NORMAL stale/no-op (no Attempt/Event, not a retryable DB error)
UoW 1 (short): guarded claim -> Attempt 1 (flush) -> job_started Event (carries the APP-generated correlation/idempotency key in its metadata) -> COMMIT (only if all succeed)
long/paid Provider call = OUTSIDE any DB transaction (DB can't roll back its execution/charges/side effects; holding a tx exhausts the pool)
commit the correlation key BEFORE the call, in the job_started Event metadata (Day46 has NO correlation column on JobAttempt; AttemptRepository.create() does NOT take it); persist the Provider request ID LATER (it can't be the only recovery identity)
UoW 2 (short) = Day33 atomic completion pack, ONE commit: guarded finish Attempt (SET finished_at, provider_request_id, cost_micros WHERE finished_at IS NULL RETURNING; provider evidence in the SAME statement, may be None->NULL and None does NOT assert a verified value; 0 rows=stale/no-op, never overwrite a finished Attempt) -> guarded Job running->succeeded (WHERE job_id AND tenant_id AND job_status='running' RETURNING; 0 rows=stale/no-op incl. WRONG TENANT, no Artifact/Event) -> ResultArtifact reference (Object Storage key, NOT bytes) -> job_succeeded Event -> COMMIT; any step fails -> rollback WHOLE UoW (no partial durable state; DB rollback does NOT delete external bytes)
guarded completion (concurrency: one still-valid running writer) != jobs_succeeded_has_finished_at CHECK (state invariant)
definitive failure (401/rejected) -> failed; timeout/UNKNOWN remote outcome -> first-class recovery state; NEVER blindly requeue/re-call (cost + duplicate effects)
```

### Reads / evidence

```text
do NOT return a detached ORM object for lazy serialization after UoW close (DetachedInstanceError / MissingGreenlet); build an allowlisted Day44 Pydantic DTO INSIDE the UoW
a mock asserting rollback() proves code-path INTENT only; PostgreSQL runtime proof = a NEW Session after failure shows Job still queued, no Attempt/Event
SQLite is NOT PostgreSQL evidence (app schema, PostgreSQL types/defaults/constraints, PostgreSQL tx/concurrency)
code rollback != durable-data rollback != external-side-effect rollback
```

### Weak vs strong (Day47)

```text
Weak:   "Share one AsyncSession and wrap the Provider call in the transaction."
Strong: "Engine/factory are process-scoped; each Job gets a fresh UoW/Session; the paid Provider call runs OUTSIDE the transaction."

Weak:   "A guarded UPDATE returning zero rows is a failure to retry."
Strong: "Zero rows is a normal stale/no-op; another Worker claimed it — create no Attempt/Event, don't retry."

Weak:   "Persist the Provider request ID after the response."
Strong: "Commit an app-generated correlation key BEFORE the call; the Provider ID comes later and can't be the only recovery identity."

Weak:   "If commit() raised, the write didn't happen."
Strong: "A commit exception is an unknown outcome; roll back/close and reload durable truth by id via a new Session."

Weak:   "A mocked rollback (or SQLite) proves the database rolls back."
Strong: "A mock proves code intent; real proof re-reads committed truth via a new PostgreSQL Session; SQLite isn't this contract."
```

### One-line mental model

```text
Day47 drives the Day46 mapping through two short guarded UoWs (explicit commit; repos never commit) around a Provider call that lives
OUTSIDE the transaction; correlation evidence is committed first, and unknown outcomes are recovered via a new guarded UoW, never blindly replayed.
```

Validation: REAL fake-session control-flow tests executed (Python 3.10.12, SQLAlchemy 2.0.29, greenlet 3.5.4, pytest 7.4.3 -> 29 passed;
deps pinned in `projects/ai-backend-data-layer/api/requirements-day47.txt`). A mock is NOT database proof: PostgreSQL runtime NOT RUN
(no server/driver; SQLite is not PostgreSQL evidence). FastAPI/Worker integration, real Provider, Object Storage, production NOT RUN.
Alembic = Day48; upload workflow = Day49; idempotent acceptance/Outbox = Day50.

Related: [Day47 lesson](../docs/fastapi/day47-async-sessions-transactions-repository-and-unit-of-work.md) · [Day47 design](../projects/ai-backend-data-layer/api/day47-async-persistence-boundary-design.md) · [code](../projects/ai-backend-data-layer/api/day47_async_uow.py) · [tests](../projects/ai-backend-data-layer/api/test_day47_async_uow.py)

---

## Day48 Alembic and Safe AI Backend Schema Evolution

Central rule:

```text
A migration = a versioned transition across SCHEMA + HISTORICAL ROWS + EVERY deployed writer. `alembic upgrade head` success
is DDL-on-one-database evidence ONLY. Safe evolution = Day36's Expand -> Backfill -> Validate -> Switch -> Contract, each
SEPARATELY GATED. Alembic is a deployment control plane != FastAPI startup != a Day47 request/Job UoW.
```

### Expand / Backfill / Validate

```text
EXPAND (0002): ADD COLUMN ... NULLABLE, NO fabricated default, NO constraint = the OLD/NEW COMPATIBILITY WINDOW (old Writers can still write a running-without-Lease row). Never fabricate historical Lease.
CONSTRAINTS (0003, SEPARATE): add CHECK ... NOT VALID (triple coherence + Day36 jobs_running_requires_lease) ONLY AFTER old Writers are DRAINED/ISOLATED. NOT VALID skips the legacy SCAN but ENFORCES every future write by ANY Writer version (old Worker writing a running-without-Lease row -> REJECTED). NOT VALID != "old Workers unaffected".
  + ADD CONSTRAINT ... CHECK (...) NOT VALID  -> protects EVERY future INSERT/UPDATE now, tolerates legacy rows.
  Deploy Expand FIRST and alone (old Workers coexist because they ignore nullable cols). No Backfill loop / no Provider in upgrade().
BACKFILL (operational, NOT in upgrade()): short tx + FOR UPDATE SKIP LOCKED batches, idempotent, restartable (DB state=checkpoint).
  candidate = running AND lease_owner IS NULL AND NOT EXISTS(row in app.job_lease_reconciliation). Fill ONLY running Jobs with trusted evidence; No Provider.
  unknown-running -> ROUTE via INSERT INTO app.job_lease_reconciliation (job_id, reason) ... ON CONFLICT (job_id) DO NOTHING (an INDEPENDENT queue table, NO app.jobs write, NO fabricated lease) so it leaves the AUTOMATIC candidate set -> the auto-loop TERMINATES and a restart never re-selects it.
  WHY a queue table not a marker column: after 0003 jobs_running_requires_lease REJECTS any UPDATE that leaves a row running+NULL-Lease (23514); a SET lease_backfill_state='reconcile' UPDATE is exactly that. Routing writes only the queue, so it is LEGAL after the strict constraint. (fake-session tests can't see the CHECK -> the real-PG bug hid behind them.)
  BUT queuing = TRIAGE, not RESOLUTION: Day36 core CHECK jobs_running_requires_lease (job_status<>'running' OR lease triple NOT NULL) NOT VALID in 0003, VALIDATEd in 0004. A queue-routed running Job with NULL Lease STILL violates it.
  automatic_backfill_candidates (running + lease_owner NULL + not in queue) != unresolved_running_without_lease (ALL running app.jobs + lease_owner NULL, INCLUDING queue-routed = Day36 remaining_targets; count joins no queue). VALIDATE/Switch/Contract require unresolved==0.
  RESOLVING A QUEUED ROW = a SEPARATE path (the automatic loop never re-selects a queued Job, matching real SQL): run_reconciliation_resolution selects DUE resolution_status='open' records (JOIN app.jobs, next_attempt_at <= now(), still running+unowned, ORDER BY next_attempt_at, FOR UPDATE OF r SKIP LOCKED) and, when trusted evidence appears LATER, in ONE short tx: guarded UPDATE app.jobs writes the Lease triple THEN — only if that UPDATE affected the row — close_reconciliation_record marks it resolved. A 0-row UPDATE does not close it (idempotent/restartable). Only a real Lease write drives unresolved -> 0.
  NO EVIDENCE YET -> defer_reconciliation_record: a QUEUE-ONLY short UPDATE bumps check_attempts+last_checked_at and pushes next_attempt_at = now() + exponential capped backoff (60s..1h). Record stays 'open'; no Lease fabricated, no requeue, no app.jobs/job_status touch, no Provider. Since the selector only returns DUE records, the SAME record isn't re-selected -> run_reconciliation_resolution TERMINATES even with max_batches=None (termination = due-filter + forward backoff, NOT a mocked empty batch). This is reconciliation POLLING/BACKOFF, NOT Job retry, NOT Provider retry.
  RESOLUTION only via (a) trusted Lease backfill (apply_lease_evidence sets the Lease triple on app.jobs; close_reconciliation_record audits the queue separately) or (b) audited real recovery ROUTED by classify_unknown_running_recovery (NON-mutating): verified 'succeeded' -> Day47 guarded completion UoW (finished_at+Artifact+Event), 'failed'/'cancelled' -> guarded terminal-recovery, unverified -> KEEP_UNKNOWN, 'queued'/'running'/bad status -> UnsafeRecoveryError. NEVER a requeue, NEVER a bare status flip. run_backfill reports unresolved so "loop stopped" != "history compliant".
  Classify: queued/terminal = no Lease; trusted-running = backfill; unknown-running = route to reconciliation queue (triage). app.job_lease_reconciliation is an independent Expand table (job_id FK, reason, routed_at, resolution_status, UNIQUE(job_id)).
VALIDATE (SEPARATE revision): ALTER TABLE ... VALIDATE CONSTRAINT -> proves HISTORY; FAILS until legacy truly resolved (exception queue != resolution).
NOT VALID = protect the FUTURE now; VALIDATE = prove the PAST later. UPDATE...RETURNING is the Day47 runtime guard, NOT the migration mechanism.
```

### Switch / Contract / graph / evidence

```text
SWITCH: EVERY Writer (Workers/recovery/admin-scripts/completion-failure) uses the token protocol; the OLD path CANNOT write. Not merely a new binary.
CONTRACT: destructive + LAST; only after Validate + Switch + evidence + observation. Once real Lease data/Provider side effects exist -> FORWARD-FIX + reconcile, NOT a destructive downgrade (a downgrade is not a time machine).
revision/down_revision = the graph + required predecessor (downgrade = reverse traversal). Parallel revisions -> multiple heads -> alembic MERGE revision.
autogenerate = a CANDIDATE diff to REVIEW (DDL/data/locks/multi-version); Day46 Base.metadata = INPUT, PostgreSQL = authority.
BASELINE/stamp: `alembic stamp <baseline>` writes alembic_version and does NO DDL -> only after PROVEN exact match. New DB: raw SQL -> stamp -> upgrade; existing DB: prove -> stamp -> upgrade later revisions. alembic_version = a version DECLARATION, not a proof.
env.py stays MINIMAL (DB config + Base.metadata + execution); app must NEVER self-run migrations on startup. DB URL resolves `-x db_url=` > env DAY48_ALEMBIC_DATABASE_URL; alembic.ini sqlalchemy.url is a NON-CREDENTIAL OFFLINE-render placeholder ONLY (NOT an online fallback) -> ONLINE fails fast without an external URL; commit no real URL. CREATE INDEX CONCURRENTLY is NON-transactional (never in a migration tx; a failed build leaves an invalid index to inspect/repair).
EVIDENCE: static/offline (ScriptDirectory + `alembic upgrade --sql` render) proves TEXT/STRUCTURE; real PostgreSQL proves BEHAVIOR (NOT VALID/VALIDATE/locks). SQLite/fake-session/`upgrade`-success are NOT PostgreSQL proof.
Provider/Object Storage outside DB tx; interrupted call = UNKNOWN outcome; Outbox intent != Provider-success proof; recover via Job/Attempt/Event + correlation/idempotency.
```

### Weak vs strong (Day48)

```text
Weak:   "Autogenerate NOT-NULL Lease columns with defaults, upgrade on startup, downgrade if it breaks."
Strong: "Expand nullable + NOT VALID; backfill only provable running ownership off the migration; VALIDATE; Switch closes the old path; Contract after observation; forward-fix, not downgrade."

Weak:   "alembic upgrade head succeeded, so the migration is safe."
Strong: "That's DDL on one DB. History, old Workers, and Provider side effects need gated phases + real evidence."

Weak:   "Exclude the violating rows so VALIDATE passes."
Strong: "A failing VALIDATE means backfill/reconciliation isn't done; an exception queue is not resolution."

Weak:   "Downgrade to undo the migration."
Strong: "After real data/side effects, forward-fix and reconcile; a destructive downgrade loses data and double-executes paid calls."

Weak:   "stamp the DB and it's at that version."
Strong: "stamp does no DDL; only stamp after independently proving the schema matches."
```

### One-line mental model

```text
Alembic records schema change as a reviewable revision graph; safe evolution is Expand/Backfill/Validate/Switch/Contract gated by real
evidence; the Day47 UoW is one short business tx while Alembic is deploy-time schema evolution; after real data, forward-fix, never destructive downgrade.
```

Validation: REAL static/offline evidence executed — Alembic revision-graph + migration-source inspection (ScriptDirectory) and
FAKE-SESSION backfill control flow (Python 3.10.12, Alembic 1.13.1, SQLAlchemy 2.0.29, pytest 7.4.3 -> 44 passed), plus an offline
`alembic upgrade --sql` DDL render (no DB connection). **PostgreSQL runtime NOT RUN** (SQLite/fake/`upgrade`-success are not PostgreSQL
proof); FastAPI/Worker integration, real Provider, Object Storage, and production migration NOT RUN. Upload workflow = Day49; Outbox/Celery = Day50/Day55.

Related: [Day48 lesson](../docs/fastapi/day48-alembic-and-safe-ai-backend-schema-evolution.md) · [Day48 design/runbook](../projects/ai-backend-data-layer/api/day48-alembic-safe-schema-evolution-design.md) · [alembic](../projects/ai-backend-data-layer/api/day48_alembic) · [backfill](../projects/ai-backend-data-layer/api/day48_lease_backfill.py) · [tests](../projects/ai-backend-data-layer/api/test_day48_alembic.py)

---

## Day49 Upload Sessions, Object Storage and Artifact Verification

```text
Upload success   = storage-layer fact      Verified = business fact + evidence
Upload Session   = temporary server-owned workflow state (initiated/uploading/verified/failed/expired)
Presigned URL    = scoped short-lived BEARER credential (replayable until expiry; NOT identity; NOT one-time)
Bucket+key+version = deterministic immutable identity   (ETag != SHA-256)
Document         = durable verified INPUT reference (not bytes)
ResultArtifact   = durable verified OUTPUT reference for a JobAttempt (not bytes)
```

Rules:
- Server owns key identity at session creation; filename is untrusted; completion rejects a client-supplied key != persisted key.
- Verify = frozen EXPECTED (size/sha256/type, frozen before upload) == TRUSTED OBSERVED (inspect storage). NEVER overwrite the expectation; NEVER accept ETag as SHA-256; a missing full-object SHA-256 is a hard mismatch. Mismatch -> failed/quarantine, no Document, no Job.
- Content/security gates are SEPARATE from byte integrity. Mandatory scan outage = FAIL-CLOSED (keep waiting, bounded backoff, no Document); unsafe = failed/quarantine. 2 GB scan never inside a request tx. Malware-clean != content-trustworthy (prompt injection).
- Finalization: inspect+verify+scan OUTSIDE db tx -> short guarded UoW creates exactly one Document + flips session verified atomically. Already verified -> return existing. DB commit fail -> re-inspect the same deterministic object, DO NOT re-upload. Stable identity = upload_session_id + guarded transition + UNIQUE(documents.upload_session_id) (NOT Day50's client idempotency key).
- Completion vs cleanup: serialize on DB state (FOR UPDATE / guarded UPDATE); NEVER hold a DB lock across storage I/O. Cleanup commits expired first, then deletes exact unverified object/version outside the tx; failed delete = recoverable orphan. Verified/documented session is NEVER deleted.
- Three lifecycles: session expiry (stop accepting completion) | credential expiry (storage stops honoring signature) | cleanup eligibility. cleanup_not_before = credential_expiry + clock_skew + safety_buffer (12:00 + 2m + 1m = 12:03).
- Multipart (2 GB): upload_id + per-part short creds + bounded parts. Part success = transport progress, NOT a final object, NOT a Document. Timed-out Complete = UNKNOWN: inspect deterministic final object first; absent -> inspect upload_id/parts; never blindly restart. Evidence is a bound tuple, not a checksum string.
- Output ordering: upload bytes -> verify immutable evidence -> short UoW inserts ResultArtifact+JobEvent + guarded Job succeeded. NEVER mark succeeded before the result reference commits. Crash after verified upload, before DB completion -> inspect object, idempotent guarded completion, DO NOT re-call the paid Provider; missing/inconsistent evidence -> preserve unknown.
- Provenance: UNIQUE(upload_session_id) = at-most-one Document; composite FK (tenant_id, upload_session_id) ON DELETE RESTRICT = same-tenant provenance (NOT authorization; Day52). No exactly-once across PostgreSQL + Object Storage.
- Secrets: presigned URL is a bearer secret (TLS-only, redact from logs, never store as Artifact identity); CORS is not authorization; no real creds/buckets/tokens/signed query strings committed.

Least-privilege presigned grant: exact op/method + bucket + EXACT key + expiry + size policy + expected checksum + allowed content-type. Never list/read-other/delete/arbitrary-key/copy/admin/ACL/long-lived creds.

### Weak vs strong (Day49)

Weak: "Storage returned 200, so I create the Document and start the Job."
Strong: "200 is a storage fact. I verify key/version/size/full-checksum + security against a frozen expectation outside the DB tx, then create exactly one Document in a short guarded UoW. Unknown outcomes are reconciled from the deterministic object, never blindly retried, and I never re-call a paid Provider on recovery."

Hardened (review rounds 1-2): finalize is legal-state + expiry guarded. It takes a VERIFICATION LEASE (owner/fencing token + `verification_hold_until`) via guarded CAS `claim_verification` and BINDS the exact object version BEFORE scanning; the scan holds NO DB lock but cleanup sees the live lease (KEEP_VERIFICATION_HOLD) and refuses. After scan, guarded CAS `commit_document_if_owner` creates the Document + flips verified ONLY if still verifying + still our token + not session-expired + cleanup hasn't won (else `lease_lost`/`cleanup_won`; EXPIRED is never flipped back to VERIFIED). `claim_cleanup` commits `expired` first, then returns an EXACT-version ref (binding it if unbound) or NO_OBJECT_PRESENT — never a version=None delete; `execute_cleanup_delete` returns DELETED or VERSION_ABSENT_RECONCILE (never a false success). Completion/cleanup determinism is proven by INTERLEAVING fake-adapter tests (scanner calls claim_cleanup mid-scan). Object adapter is create-only + version-history (exact-version inspect/delete). Server owns bucket+key (+ bound version); completion rejects client identity (REJECTED_IDENTITY) and verifies observed bucket/key/version/size/sha256/content-type. Finding 3: credential expiry != stored-object invalidation — after credential expiry (before session expiry) completion still verifies+completes an already-uploaded object; absent -> UPLOAD_WINDOW_EXPIRED, still present+valid cred -> OBJECT_NOT_FOUND; only session expiry or a cleanup-won claim stops completion.
Schema honesty: the published upload_sessions allowlist has NO `verifying`, no owner/lease token, no `verification_hold_until`, no bound-version column; all are MODELED in-memory. The REAL schema needs a Day48-safe FORWARD migration (a `verifying` status + owner/hold columns via a branch revision, or a verification-lease table, plus a bound-version column) — not implemented here; never a rewrite of published Alembic history; no real PostgreSQL runtime claimed.

Validation: FAKE in-memory Object Storage adapter — application CONTROL FLOW only, incl. a MODELED atomic UoW (Python 3.10.12, pytest 7.4.3 -> 44 passed; stdlib-only module). **NOT** real presigned/checksum/multipart/versioning semantics, **NOT** PostgreSQL runtime, **NOT** a real Object Storage integration, **NOT** production. Day50 Outbox / Day51 JWT / Day52 authorization / Day55 Celery / real Provider NOT implemented.

Related: [Day49 lesson](../docs/fastapi/day49-upload-sessions-object-storage-and-artifact-verification.md) · [Day49 design/runbook](../projects/ai-backend-data-layer/api/day49-upload-object-storage-and-artifact-verification-design.md) · [model](../projects/ai-backend-data-layer/api/day49_upload_verification.py) · [tests](../projects/ai-backend-data-layer/api/test_day49_upload_verification.py)

---

## Day50 Idempotent AI Job API and Transactional Outbox Integration

```text
Idempotency-Key = identity of ONE logical client command   fingerprint = evidence semantics didn't change (key NOT in fingerprint)
UNIQUE(tenant_id, idempotency_key) = DB arbiter of concurrent acceptance (NOT app SELECT-then-INSERT)
Job + exactly one job.dispatch_requested Outbox intent = ONE atomic short UoW (both or neither)
Outbox = durable dispatch obligation   Relay = at-least-once delivery   published_at = checkpoint, NOT Job success
```

Acceptance (`POST /jobs`):
- missing/blank Idempotency-Key -> reject BEFORE any DB write. Every referenced Document must be Day49-verified + tenant-owned else reject.
- same key + same fingerprint -> return the original Job (no 2nd Job/intent). same key + changed semantics -> 409 CONFLICT (no durable facts).
- fingerprint covers ALL behavior-changing fields (docs refs, prompt, model/profile, output contract, token/quality, api version). Doc order canonicalized ONLY for an explicitly unordered contract; else order preserved.
- DB is the arbiter: `INSERT ... ON CONFLICT (tenant_id, idempotency_key) RETURNING`. SELECT-then-INSERT fails because BOTH see absence and create duplicates.
- retention is an explicit retry-contract window; an expired record must NOT make a late retry look like a new command. Client rule: fresh never-reused key per command.

Atomic UoW: validate -> create Job(queued) + one dispatch intent in the SAME tx -> commit both or roll back both. Never 202 for a Job with no dispatch intent. At-most-one dispatch intent per Job = logical UNIQUE(job_id, event_type).

Relay: API UoW NEVER publishes inside the DB tx. After commit: claim DUE unpublished intents (FOR UPDATE SKIP LOCKED + lease/owner) -> publish OUTSIDE the lock via TransportAdapter.publish(envelope) -> fenced checkpoint sets published_at.
- envelope small+stable: outbox_event_id, event_type, job_id, correlation id. Queue is NOT Job truth; Worker re-reads Job by job_id. No prompt/secret/mutable-doc in the message.
- publish then crash before published_at -> unknown -> retain (published_at NULL) + republish later (at-least-once duplicate). Never delete/guess.
- transient failure -> keep event, attempt_count++, REDACTED error, next_attempt_at = bounded exp backoff + jitter, release lease, retry when due.
- exhausted/permanent -> QUARANTINE (retain + alert + controlled-replay). Do NOT delete, do NOT mark the Job failed.
- multi-relay: short DB claim + lease; NO lock over transport I/O (long external I/O expands tx, blocks progress, lock waits/timeouts, and can't make a cross-system tx). Fencing token: a stale relay whose lease expired cannot write published_at after a new owner took over.

Four idempotency layers: (tenant,key)=acceptance | UNIQUE(job_id,event_type)=dispatch intent | guarded queued->running RETURNING=worker execution | provider correlation/evidence=post-call recovery (Day53).
Worker: duplicate delivery allowed; execution authority ONLY on guarded `UPDATE ... WHERE job_status='queued' RETURNING` (zero rows -> NO Provider call).

NO exactly-once across PostgreSQL + broker + Worker + Provider. Use durable identity + guarded transitions + idempotent recovery + evidence retention.

Schema honesty: published schema HAS UNIQUE(tenant_id, idempotency_key); it LACKS a request-fingerprint column, UNIQUE(job_id,event_type), and relay ops columns (attempt_count/last_error/next_attempt_at/dispatch-quarantine state/relay owner+lease+fencing token) — all MODELED in-memory. Real schema needs a Day48-safe FORWARD additive migration; not implemented here; no published Alembic revision rewritten.

### Weak vs strong (Day50)
Weak: "one idempotency key + at-least-once = exactly-once."
Strong: "Client (tenant,key) makes acceptance idempotent; Job+Outbox commit atomically; a Relay delivers at-least-once after commit; duplicates are absorbed by a guarded Worker claim. I never claim exactly-once across the broker/Worker/Provider."

Review round 1 (P1): (1) acceptance conflict arbitration is ONE atomic op (`upsert_job_on_conflict` under a lock modeling `INSERT ... ON CONFLICT`) — a bare read-then-insert lets two concurrent requests both create; forced-interleaving thread test -> one CREATED + one RETURNED_EXISTING, 1 Job, 1 intent. (2) checkpoint/failure-recording require a LIVE lease (owner match AND now < relay_hold_until) — an EXPIRED relay is fenced even before takeover, published_at stays NULL. (3) idempotent-retry ordering: same key+fingerprint returns the original Job BEFORE the mutable Document admission check (an exact retry survives a Document later becoming unavailable); Documents are validated only for a NEW command.
Validation: FAKE in-memory store + transport — application CONTROL FLOW only (Python 3.10.12, pytest 7.4.3 -> 29 passed; stdlib-only module). NOT PostgreSQL UNIQUE/tx/isolation/ON CONFLICT/SKIP LOCKED, NOT a real broker/Celery (ACK/redelivery/poison), NOT Worker/Provider runtime, NOT integration/production. Day51 auth / Day52 authz+quota / Day53 real Provider / Day55 real Celery not implemented.

Related: [Day50 lesson](../docs/fastapi/day50-idempotent-ai-job-api-and-transactional-outbox-integration.md) · [Day50 design/runbook](../projects/ai-backend-data-layer/api/day50-idempotent-job-acceptance-and-transactional-outbox-design.md) · [model](../projects/ai-backend-data-layer/api/day50_job_acceptance_outbox.py) · [tests](../projects/ai-backend-data-layer/api/test_day50_job_acceptance_outbox.py)

---

## Day51 Authentication, Password Security and JWT

```text
Password hash   = one-way verification evidence (adaptive Argon2id; NEVER plaintext/reversible; SHA-256 too fast for passwords)
Signed JWT      = short-lived, READABLE-but-tamper-evident identity credential (integrity/authenticity, NOT secrecy)
Refresh Session = server-owned, revocable, PER-DEVICE state (store the token HASH, not the raw token)
AuthN = trusted user_id (verified sub)   AuthZ = Day52 decides what the user may do
```

Passwords:
- store an adaptive hash only (Argon2id, library salt + work factor). Login: library `verify(candidate, stored_hash)` — do NOT re-hash+compare (hash encodes algo/salt/cost).
- ONE generic auth failure for unknown account AND wrong password (anti-enumeration; decoy verify for unknown user). On success, `needs_rehash` to upgrade; never keep plaintext.
- a high-entropy random REFRESH token may use a fast SHA-256 digest (not enumerable) — do NOT generalize to passwords.

JWT (asymmetric RS256):
- payload is READABLE. Put only sub/iss/aud/iat/exp/jti. NEVER password hash, provider key, prompt, Document content, secret, or client tenant.
- verification is a CONTRACT, not a decode: pin algorithm (allowlist, reject alg=none / HS256-confusion), select a TRUSTED key by allowlisted kid, verify signature + iss + aud + exp + nbf + require sub -> AuthenticatedIdentity(user_id=sub). tenant_id in the body is NOT trusted (Day52).
- keys: Auth Service holds the PRIVATE signing key; verifiers hold PUBLIC keys only (symmetric would let every verifier sign). kid is an allowlist id, NEVER a URL/file/lookup. Unknown kid -> refresh once from a preconfigured trusted source, else reject 401 + safe event.
- rotation K1->K2: publish K2, trust K1+K2, sign with K2, keep K1 verify for its max token lifetime + skew, then drop K1. Confirmed K1 compromise -> revoke K1 immediately (before expiry), force reauth.

Access vs Refresh:
- short Access Token limits theft window but gives NO immediate logout/password-change revocation (needs server-side session/security-version state).
- per-device AuthSession: session_id/user_id/token_family_id/refresh_token_hash/created/expires/revoked/last_rotated/rotation_counter + grace fields.

Refresh rotation (guarded, atomic):
- one `UPDATE ... WHERE current_hash + active + not-expired RETURNING` = SOLE winner; zero rows -> issue nothing. All rotation facts commit together or roll back together (fail after marking A used but before B -> rollback keeps A valid).
- bounded ONE-TIME retry grace recovers the SAME usable token B (never A->C) from a short-TTL ENCRYPTED recovery slot for a lost response; residual small replay risk. ANY used family token AFTER grace (a per-family used-hash ledger catches replay of any earlier token, not just the latest) = REPLAY_DETECTED -> reject + revoke family + RETAIN the token_family (audit evidence; do NOT delete) + isolate other devices, clear recovery material, require reauth.
- recovery material has a MINIMUM-RETENTION lifecycle: it lives only until retry_grace_expires_at. `sweep_expired_recovery_material(now)` destroys recovery_ciphertext + grace_result_token_hash for every past-grace session EVEN IF the old token never returns (fail-closed on time), while RETAINING the used-token ledger + audit (post-grace replay stays REPLAY_DETECTED, not INVALID). ALL revoke paths (revoke_session, family revoke, revoke_all_user_sessions) destroy recovery material IMMEDIATELY via a shared `_clear_recovery_material` helper (logout-all / password change / account-security events do not wait for the sweep); the sweep is ONLY the expiry fallback for an abandoned token. Real deployment MUST run the sweep as a scheduled job (cron / pg_cron); never rely on the client retrying.
- concurrent rotate of A -> one ROTATED + one GRACE_RETRY (one session/family, one new token).

Browser/CSRF: Refresh in HttpOnly + Secure + appropriate SameSite Cookie (NOT JS-readable JSON / localStorage). HttpOnly blocks JS reads, NOT auto cookie attachment -> NOT CSRF defense. State-changing cookie endpoints: SameSite + Origin (+Referer) + CSRF token/custom header; SameSite=None requires Secure + explicit CSRF. Reject cookie-only cross-site without valid Origin + CSRF.

### Weak vs strong (Day51)
Weak: "A signed JWT is secure, so I store the tenant + a secret in it and decode it server-side."
Strong: "A JWT is readable; I keep secrets out, verify the full contract (alg/key/sig/iss/aud/exp/nbf/sub), trust only sub, and let Day52 decide tenant authority. Refresh uses per-device hash-stored sessions with a guarded RETURNING rotation; replay after grace revokes + retains the family evidence."

Schema honesty: users already have a unique identity; a `password_hash` column and the per-device `AuthSession` table (token_family_id, refresh_token_hash, rotation/grace/revoke) are new facts — MODELED in-memory here; the real schema needs a Day48-safe FORWARD additive migration (not implemented; no published Alembic revision rewritten).

Validation: REAL Argon2id (argon2-cffi) + REAL RS256 JWT (PyJWT + cryptography) with EPHEMERAL in-process keys + an in-memory guarded-rotation store (Python 3.10.12, argon2-cffi 23.1.0, PyJWT 2.8.0, cryptography 48.0.0, pytest 7.4.3 -> 37 passed). Proves crypto primitives + control flow ONLY. NOT real PostgreSQL (UNIQUE/tx/isolation/UPDATE...RETURNING), NOT FastAPI/browser (cookies/SameSite/Origin/CSRF at the wire) / JWKS endpoint, NOT integration/production. JWE (encrypted JWT) out of scope. Day52 authz/quota, Day53 real Provider, Day55 real Celery not implemented. No plaintext passwords / refresh tokens / JWTs / operational signing keys committed.

Related: [Day51 lesson](../docs/fastapi/day51-authentication-password-security-and-jwt.md) · [Day51 design/runbook](../projects/ai-backend-data-layer/api/day51-authentication-password-security-and-jwt-design.md) · [model](../projects/ai-backend-data-layer/api/day51_authentication_jwt.py) · [tests](../projects/ai-backend-data-layer/api/test_day51_authentication_jwt.py)

---

## Day52 — Authorization, Tenant Isolation, Quotas and API Security

Mental model: authentication (Day51) = a trusted `user_id`; authorization (Day52) = active Membership + role action + resource scope. A client `tenant_id` is a SELECTOR, never authority; authority is the server-built `AuthorizedTenantContext(user_id, tenant_id, permissions)`.

AuthN vs AuthZ:
- Day51 JWT proves `user_id` only; the body/header `tenant_id` is unauthenticated input ("因为请求中的tenant可以被修改。").
- JWT role claims are NOT sole long-lived authority: Membership removal / role downgrade stays stale until token expiry -> check current active Membership + role per protected request (or an explicit cache/revocation trade-off).

User/Tenant/Membership/role/action:
- `tenant_memberships(user_id, tenant_id, role, status)` = many-to-many authority; Tenant-A authority never becomes Tenant-B authority.
- A role is a maintainable SET OF ACTIONS whose names match the effect: `job.create`, `job.read_own`, `job.read_all`, `job.cancel`, `job.retry`. `POST /jobs/{id}/cancel` = `job.cancel` (NOT `job.create`); retry = `job.retry`.
- `authorize(identity, requested_tenant_id, action)` -> active Membership -> role permissions -> require action; every failure is a GENERIC 403 (no resource/tenant/role revealed).

Tenant + resource isolation (IDOR/BOLA safe):
- Build `AuthorizedTenantContext` only after verified identity + active Membership + action. Scope EVERY query: `WHERE tenant_id = :authorized_tenant_id AND job_id = :job_id`.
- `job.read_own` ALSO requires `created_by_user_id = :authenticated_user_id` (role selects the rule; owner predicate proves ownership; same-tenant colleague is not "own").
- Tenant-scoped miss -> public **404** (no existence oracle); missing action -> generic **403**. FastAPI Dependencies centralize policy but do NOT constrain SQL -> repositories carry the context. RLS = optional defense in depth; its tenant context must come from `AuthorizedTenantContext`, never Header/Body (watch pooled connections + bypass roles).

Safe boundary: public errors never reveal another tenant's resource/tenant/role. Audit = metadata only (trace ID, actor, tenant scope, resource, action, decision, policy version); NEVER log raw JWTs/Refresh Tokens/passwords/Provider keys/prompts/Document content. CORS = browser-origin policy, NOT authn/authz (Day51 cookie+Origin+CSRF is separate).

Rate limit vs quota vs concurrency:
- Rate limit = speed; quota = accumulated tokens/cost; concurrency = in-flight/Worker pressure. Different systems.
- Local per-instance counters undercount: 4 instances × 100 ≈ 400 -> use a SHARED atomic coordinator (Redis) for rate limiting, NOT as durable budget truth.
- Keys: `tenant+action` (capacity), `tenant+user+action` (member abuse), IP only auxiliary (client `X-Forwarded-For` ≠ identity; trusted-proxy config is deliberate).
- Limiter DOWN on paid `POST /jobs` = FAIL-CLOSED -> 503, NOT 429 (429 = healthy limiter confirmed a breach). Fixed window = edge bursts; sliding = smooth at cost; token bucket = bounded burst (cap 20) + refill (100/min) -> fits Job creation. Normal 429 has `Retry-After` + stable code; client obeys or jittered backoff, SAME Idempotency-Key.

Durable token/cost quota (PostgreSQL is the arbiter):
- Validate per-Job `max_tokens`; guarded `UPDATE tenant_budgets SET reserved_tokens = reserved_tokens + :amt WHERE token_limit - used_tokens - reserved_tokens >= :amt RETURNING` — one row = reserved, zero rows = no reservation + no acceptance ("由数据库的update returning").
- Reservation + Job + Outbox commit in ONE tx; failure rolls all three back ("回滚") — no ghost reservation, no unfunded Job.
- Reconcile actual usage: `actual <= reserved` -> settle EXACT actual into `used_tokens` + release remainder; `actual is None` -> keep reservation, `reconciliation_pending`; `actual < 0` -> reject (ValueError); `actual > reserved` (**overage**) -> `OVERAGE_RECONCILIATION_REQUIRED`: keep reservation, record exact observed + reason, NEVER `min()`-truncate or release as settled (a real cost fact must not be lost). Reserve TOTAL billable cost, not only `max_tokens`; Day53 Provider adapter owns estimate/headroom + overage policy.
- reconcile is IDEMPOTENT (at-least-once callbacks/polling/recovery): a per-job lifecycle status (`RESERVED -> {PENDING} -> SETTLED | OVERAGE_RECONCILIATION_REQUIRED`) makes a repeat SAME actual a no-op (no budget change), a DIFFERENT actual after `SETTLED` a `RECONCILIATION_CONFLICT` (no re-settle, no fake overage, facts+audit kept), and any plain reconcile after overage a no-op. Only the explicit `settle_overage(job_id, granted_extra_tokens=0)` may change an overage's budget fact and it NEVER bypasses the hard quota: it settles the FULL observed usage to SETTLED only when `available` stays >= 0 (tenant headroom, or a TRUSTED ops/accounting credit covers the shortfall in the same atomic step — `granted_extra_tokens` is a billing/ops-approved top-up, NOT a client field); otherwise no budget change, stays OVERAGE_RECONCILIATION_REQUIRED (never negative available). Idempotent (no double credit/charge/release); OverageRecord + exact usage + granted credit retained.

Idempotency ordering (admission): authorize -> same-command tenant-scoped recovery FIRST (no new cost, no rate-limit charge) -> rate-limit NEW commands -> guarded reserve + Job + Outbox. The request fingerprint is SERVER-computed (`compute_request_fingerprint` = SHA-256 of canonical JSON of behavior-relevant fields `max_tokens`/`document_id`/`task_type`; never Python `hash()`, never client-asserted). Same key + same SERVER fingerprint -> original Job, NO second reservation ("返回原job"); same key + any changed behavior field -> 409, no facts. NOT an authz bypass: removed Membership blocks old-Key recovery. Optional separate low read limit for recovery.

Erroneous cancel-grant exercise: contain by rolling back the bad centralized `job.cancel` grant (fail closed for member cancel), NOT stopping safe creation. Rollback protects FUTURE traffic only; classify historical intents (actor/tenant/Job/policy version/time/Membership/state/Worker-Provider work). Guarded repair by stable intent ID + policy version; zero `UPDATE ... RETURNING` rows = facts changed -> STOP auto-repair + reconcile; never delete bad intents, never overwrite a legitimate later cancel, never blindly re-run paid Provider work.

### Weak vs strong (Day52)
Weak: "The JWT is valid and carries `tenant_id` and a role, so I trust them and load the Job by id."
Strong: "The JWT proves user_id only. I treat tenant_id as a selector, prove active Membership + the required action in that tenant, build an AuthorizedTenantContext, and scope the query by tenant (+ owner for read_own) returning 404 on a miss. I reserve tenant budget with a guarded UPDATE ... RETURNING and commit Reservation + Job + Outbox atomically; the shared limiter fails closed on a paid path."

Schema honesty: `tenant_memberships`, `tenant_budgets(token_limit/used/reserved)`, per-Job `max_tokens`, and a cancel-intent audit ledger with `policy_version` are new facts MODELED in-memory; a real deployment adds them via a Day48-safe FORWARD additive migration (no published Alembic revision rewritten). Day50 Job+Outbox reused; quota funded in that same tx.

Validation: in-memory control-flow model, standard-library only (Python 3.10.12, pytest 7.4.3 -> 32 passed). Proves APPLICATION CONTROL FLOW ONLY. NOT real PostgreSQL (constraint/tx/isolation/UPDATE...RETURNING/RLS), NOT real Redis (distributed atomics/TTL/failover), NOT FastAPI/proxy/browser (Dependency/CORS/cookie/CSRF/routes), NOT Provider/Worker/integration/production. Day53 real Provider, Day54 streaming/cancellation, Day55 Workers not implemented. No real JWT/Provider key/password/prompt/user data used.

Related: [Day52 lesson](../docs/fastapi/day52-authorization-tenant-isolation-quotas-and-api-security.md) · [Day52 design/runbook](../projects/ai-backend-data-layer/api/day52-authorization-tenant-isolation-quotas-and-api-security-design.md) · [model](../projects/ai-backend-data-layer/api/day52_authorization_tenant_quota_security.py) · [tests](../projects/ai-backend-data-layer/api/test_day52_authorization_tenant_quota_security.py)

---

## Day53 — OpenAI SDK, Provider Boundaries and Structured Output

Mental model: the Provider is untrusted at three levels — its SDK types, its output, its configuration. An application-owned boundary sits in front of all three. `Provider boundary` = an application-owned interface (`AIProvider.generate(request) -> ProviderOutcome`), NOT "the data business logic needs from the response".

Layering (SDK types stop at the Adapter): Router/Dependency -> Application Service -> `AIProvider.generate` -> `OpenAICompatibleAdapter` (owns ALL SDK objects + vendor exceptions) -> Day44 structured validation -> `CompletionService` (guarded running->succeeded, short UoW) -> Repository -> PostgreSQL. Student first said "数据库层"; corrected: the Repository is the data layer but SDK types stop EARLIER, inside the Adapter. The Adapter translates; it never completes Jobs or writes DBs.

ProviderOutcome union (application-owned): `ProviderSuccess(raw_payload UNTRUSTED, usage)`, `ProviderRefusal`, `ProviderIncomplete`, `ProviderTimeout`, `ProviderAuthenticationError`, `ProviderRateLimited`, `ProviderCapabilityError`, `ProviderTransportError`. No raw SDK type/prompt/debug field/secret escapes inward.

Validation gate (Day44, before ANY side effect): strict Pydantic model (`extra="forbid"`) — valid JSON with a forbidden `debug_prompt` or a missing required `citations` FAILS. Invalid output NEVER calls completion (no success transition / Result Artifact / Event / success write); the failure classification carries field LOCATIONS only, never values or the raw payload. Parsing != validation; citation shape != grounding (not taught).

Server-owned versioned schema: `task_type` -> a server-owned `SchemaRegistry` `(name, version)`; a Job binds name+version at acceptance; a v2 output must NOT silently satisfy a v1 Job (no implicit truncation/downgrade/guess; unknown version -> `SCHEMA_NOT_FOUND`). Day44 `output_schema` must NOT forward arbitrary client JSON Schema — constrain to server-approved families/versions.

Pre-call execution gate (a PAID side effect is claimed FIRST): `execute_job` order = claim eligibility -> Provider call -> process -> guarded completion. ATOMIC claim (`claim_for_new_call` under a lock, models a guarded `UPDATE ... WHERE status='running' AND open_attempt IS NULL RETURNING`): exactly ONE caller acquires execution rights and creates one IN_FLIGHT `Attempt`; a terminal/pending Job OR a concurrent/re-entrant caller -> `PRECALL_BLOCKED` (reason `claim_conflict`) with **transport calls == 0**, so two Workers can't both issue a paid call. The outcome is bound back to that Attempt (record `provider_request_id`); a timeout keeps the Attempt `AWAITING_LATE_OUTCOME`, else it is CLOSED. Then bind to contract: `bind_request_to_contract` derives model/schema/version/task/profile from the persisted `ExecutionContract` (caller cannot pick them); a mismatch -> `CONTRACT_MISMATCH` before any transport call; max tightened to `min(request, bound, model hard cap)`, never enlarged.

Late-outcome ingestion (PATH B): a result that arrives after a timeout is handled by `ingest_late_outcome(outcome, job_id, attempt_id, correlation_id)` — it makes NO adapter/transport call and validates the PERSISTED `Attempt` (attempt_id + correlation + provider_request_id — correlation alone is NOT proof; a request id absent at send time is first-recorded on arrival), then runs guarded completion. A TERMINAL Job -> `COMPLETION_NOOP` for ANY late outcome (invalid success / refusal / incomplete included — no Event/cost/settled_tokens/result/status change); a wrong attempt/correlation/request-id -> `LATE_OUTCOME_REJECTED`. CONCURRENCY-SAFE + IDEMPOTENT (callbacks are at-least-once): an atomic `claim_late_outcome` flips the Attempt `AWAITING_LATE_OUTCOME -> PROCESSING_LATE_OUTCOME` in one critical section, so of two concurrent/duplicate deliveries exactly ONE dispatches (one Event + one `job.cost_recorded`, `settled_tokens` written once) and the other is a `COMPLETION_NOOP`; a RECORDED `provider_request_id` must be matched EXACTLY (a MISSING incoming id is rejected, same as a different one; no recorded id yet requires a non-empty incoming id, a controlled first-record). The winner's dispatch is one UoW: snapshot pre-dispatch Job facts -> dispatch -> CONSUMED on success; on a dispatch exception roll ALL partial writes (Event/status/cost/result) back to the snapshot THEN reopen the Attempt to `AWAITING_LATE_OUTCOME` (a later legitimate redelivery yields exactly one complete result; never a Provider re-call). Calling `execute_job` a second time is NOT late-result handling (it issues a second paid Provider call). Day54 owns the real callback/streaming/cancellation protocol.

Completion + guard: only `CompletionService` runs guarded `running -> succeeded`, persists the validated Result Artifact/usage/Event, commits a short UoW. Zero rows -> STOP (duplicate/stale/cancelled/retry/changed/terminal facts); inspect + reconcile, never overwrite. Guarded completion accepts a job that is RUNNING or PENDING_RECONCILIATION (a matching late result after a timeout), never a terminal SUCCEEDED/FAILED.

Two separate axes: business execution success (valid output) vs cost settlement (usage known/unknown). A VALID output can succeed even when usage is UNKNOWN -> retain the Day52 reservation, hold `reconciliation_pending`; NEVER record unknown usage as zero. Known-usage NON-success (invalid/refused/incomplete) still settles the EXACT usage via `record_cost` (known -> SETTLED, unknown -> reconciliation_pending; refusal usage never dropped) — invalid output != Provider didn't charge. Overage stays controlled reconciliation (Day52 `settle_overage`), never `min()`-truncated.

Settings/credentials/bounds (Day45): validated Settings + Adapter own `api_key`/`base_url`/model policy (clients can modify inputs). Keys/base URLs/full Settings/arbitrary model IDs never enter Job requests/persistence/Outbox/logs; client model choice is only a constrained selector -> allowlisted model. Persist NON-secret execution-contract facts (provider profile/policy version, approved model, schema name/version, task type, max-output bound, correlation IDs). Job-controlled 5000 cap wins over an 8000 adapter default: `effective = min(Job cap, ceiling)` — never enlarge; the Adapter REPORTS usage, no second reservation. Reuse one lifespan-owned client per process (drain before close); no cross-process singleton claim.

Error semantics: refusal = classified non-success (not empty success). TIMEOUT = unknown execution/usage -> NON-terminal `PENDING_RECONCILIATION` (NOT terminal FAILED), reservation retained, no auto second call, a matching late result may still complete. 401/403 = config/auth failure -> STOP new calls with that config (`ProviderConfig.disable`) + keep safe evidence. 429 after a durable 202 = downstream Job/Attempt event, NOT a retroactive client 429 (keep safe Retry-After; Day56 owns retry). 400: a CONFIG-WIDE capability failure (model/profile can't honor the schema, `config_scope`) fails the config CLOSED (blocks the next call before transport); a single-request 400 does not disable the config. Raw minimization: do NOT default-persist raw Provider responses; a forensic raw store needs explicit minimization/redaction/access-control/retention/audit.

Rollout/rollback exercise: a rollout to a model lacking `research_summary.v1` -> new calls 400; an OLD in-flight valid v1 result (a DISTINCT call) still validates against its PERSISTED execution contract and is accepted via guarded completion. Core rule: **configuration rollback != business-fact rollback** — current Settings governs NEW calls; the persisted contract governs result acceptance.

### Weak vs strong (Day53)
Weak: "The SDK already parsed the JSON and returned a response object, so I pass it to completion."
Strong: "The Adapter translates the SDK response/exceptions into my ProviderOutcome union; the payload is untrusted until my strict Day44 model validates it against the Job's bound server-owned schema. Only then does the Completion Service run the guarded running->succeeded UoW. A valid result can succeed with unknown usage while I hold cost reconciliation-pending; a config rollback never rolls back that fact."

Validation: REAL Pydantic v2 strict validation + an in-memory Adapter->Validator->Completion model with an INJECTED FAKE transport (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 48 passed). Proves the validation gate + application control flow ONLY. NOT the real `openai` SDK/network/Provider, NOT PostgreSQL/Redis/Celery Worker, NOT FastAPI wire/integration/production. Day54 streaming/disconnect/cancellation, Day55 Celery, Day56 retry/backoff not implemented. No real api_key/prompt/Document content/Provider response persisted or logged.

Related: [Day53 lesson](../docs/fastapi/day53-openai-sdk-provider-boundaries-and-structured-output.md) · [Day53 design/runbook](../projects/ai-backend-data-layer/api/day53-openai-sdk-provider-boundaries-and-structured-output-design.md) · [model](../projects/ai-backend-data-layer/api/day53_openai_provider_structured_output.py) · [tests](../projects/ai-backend-data-layer/api/test_day53_openai_provider_structured_output.py)

---

## Day54 — AI Streaming, Client Disconnects, Timeouts and Cancellation

Mental model: THREE independent lifecycles — HTTP client connection, Provider request, durable Job — plus TWO streaming kinds. Confusing them corrupts business truth or wastes billable work.

Boundary (state it explicitly): HTTP client disconnect != the Provider call necessarily stops != an already-persisted Job auto-cancels != the accepted business commitment disappears.

Three lifecycles:
- HTTP client connection: an SSE disconnect / connection timeout ends only THAT subscription (never touches the durable Job).
- Provider request: its real state/outcome/usage may stay UNKNOWN after a disconnect or timeout.
- Durable Job: a PostgreSQL-owned business fact (queued -> running -> succeeded); it does NOT auto-cancel on disconnect. Student first said "queued running success" (wrong lifecycle), corrected to "保持running".

Two streaming kinds: (A) Provider token streaming = transient chunks for ONE Provider request; (B) durable Job progress/event streaming = safe observable state for a persisted Job (subscription/reconnection). Never treat one as the other's durable truth. Worker consumes A; browser subscribes to B.

Reconnection + persistence trade-off: a reconnecting browser reads/subscribes to durable Job state + safe progress events, NOT a Provider token replay. Do NOT default-persist every token as a JobEvent (write/storage cost + unvalidated/partial/sensitive content + breaks Day53 raw minimization). Persist low-frequency SAFE milestones; persist the final Result Artifact only after Day53 validation + guarded completion. A replayable partial-text product needs its own explicit design.

Timeout: HTTP connection timeout limits a subscription only. Provider request timeout = our side got no response in time -> execution/result/usage may be UNKNOWN -> `PENDING_RECONCILIATION`, reservation retained, no invented zero usage, no blind re-call (Day53 preserved). A later Provider timeout does NOT retroactively turn the original 202 into a 504; users observe later state via Job reads/events. The Provider may have raw output, but it does NOT create the application's Result Artifact — only Day53 validation + guarded completion does.

Durable cancellation/deadline protocol: cancel/expiry request (authorized) -> PERSIST a durable auditable INTENT FIRST (reason/timestamp/actor-or-system-source/version) — the Router must NOT write `cancelled` just because HTTP arrived ("不能") -> Worker cooperatively OBSERVES the intent at safe points -> GUARDED terminal transition (`cancelled`/`expired`) -> observable result. Pre-call: do NOT call the Provider ("是不调用并尝试 guarded transition 到 cancelled"), provider.calls == 0. Mid-stream: best-effort Provider abort/stream close + stop publishing + record safe correlation; does NOT prove remote stop or zero cost ("不能") -> unknown usage `reconciliation_pending`, reservation retained. Deadline: different trigger, same durable/auditable/cooperative/guarded constraints.

Crash + at-least-once: persist the intent FIRST because it survives process loss, is auditable, and is re-observable ("worker会再次扫描intent") — NOT because it authorizes Day56 blind retries. A restarted Worker re-observes; the guarded transition absorbs repeats (second apply -> zero rows).

Concurrency: completion and cancellation/expiry each use a guarded terminal write (`UPDATE ... WHERE status IN (live) RETURNING`). Exactly ONE wins; the loser sees zero rows and stops/reconciles ("不应该" overwrite). A late valid Provider result AFTER a terminal cancel/expiry cannot flip the Job to `succeeded` ("不能") — no Result Artifact/success overwrite.

Erroneous disconnect->cancel rollout: FIRST roll the policy back (stop new harm) — policy rollback != business-fact rollback; do NOT bulk-flip terminal Jobs to running ("不能"). Build the affected set from release VERSION + a bounded TIME WINDOW (period the bad release was active — evidence, NOT a retry delay) + stable intent IDs. Retain audit history. Evidence: a client idempotency key proves logical acceptance only, NOT Provider execution; Provider request/correlation/cost evidence decides reconciliation. Request id + unknown usage -> retain reservation + reconcile, never blind re-call ("不能").

### Weak vs strong (Day54)
Weak: "The browser disconnected, so cancel the Job; the Provider timed out, so mark it failed and retry."
Strong: "A disconnect ends only the subscription — the durable Job stays running. A timeout is PENDING_RECONCILIATION with unknown usage retained, not a failure or a blind retry. Cancellation is a durable auditable intent + cooperative Worker + guarded terminal write; completion and cancellation never overwrite (zero rows -> stop/reconcile)."

Schema honesty: the `cancelled`/`expired` terminal statuses, `PENDING_RECONCILIATION`, and a durable cancellation/expiry intent table (reason/actor/timestamp/version) are new facts MODELED in-memory; a real deployment adds them via a Day48-safe FORWARD additive migration (no published Alembic revision rewritten). Day52 reservation/reconciliation + Day53 guarded completion/Provider boundary reused.

Validation: in-memory control-flow model, standard-library only (Python 3.10.12, pytest 7.4.3 -> 15 passed). Proves APPLICATION CONTROL FLOW ONLY. NOT real FastAPI/SSE wire, NOT the real OpenAI SDK/network/Provider token stream, NOT PostgreSQL/Redis/Celery, NOT integration/production. Day55 Celery, Day56 retry/backoff not implemented. No real credentials/prompts/Document content/raw Provider tokens used.

Related: [Day54 lesson](../docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md) · [Day54 design/runbook](../projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md) · [model](../projects/ai-backend-data-layer/api/day54_streaming_disconnects_timeouts_cancellation.py) · [tests](../projects/ai-backend-data-layer/api/test_day54_streaming_disconnects_timeouts_cancellation.py)
