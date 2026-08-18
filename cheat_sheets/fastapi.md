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

Terminal-fact mapping + late-result binding: a durable intent's terminal is kind-derived (`terminal_for_intent`): user cancel -> CANCELLED, deadline -> EXPIRED — consistent across pre-call / mid-stream / post-last-token-pre-completion / crash re-observation. The `provider_request_id` is persisted at Provider-request open (so a later cancel/timeout is RECONCILE_UNKNOWN_EXTERNAL, not NO_PROVIDER_EXECUTION_EVIDENCE). A durable intent written after the last token but before completion still prevents `succeeded` (final cooperative check). A late result reuses Day53's identity binding (job_id + attempt_id + correlation_id + provider_request_id, missing == mismatch) + strict validation gate before any Artifact; mismatch/missing/not-awaiting/terminal/invalid -> side-effect-free refusal; duplicate/concurrent matched -> at most once; zero Provider calls.

### Weak vs strong (Day54)
Weak: "The browser disconnected, so cancel the Job; the Provider timed out, so mark it failed and retry."
Strong: "A disconnect ends only the subscription — the durable Job stays running. A timeout is PENDING_RECONCILIATION with unknown usage retained, not a failure or a blind retry. Cancellation is a durable auditable intent + cooperative Worker + guarded terminal write; completion and cancellation never overwrite (zero rows -> stop/reconcile)."

Schema honesty: the `cancelled`/`expired` terminal statuses, `PENDING_RECONCILIATION`, and a durable cancellation/expiry intent table (reason/actor/timestamp/version) are new facts MODELED in-memory; a real deployment adds them via a Day48-safe FORWARD additive migration (no published Alembic revision rewritten). Day52 reservation/reconciliation + Day53 guarded completion/Provider boundary reused.

Validation: in-memory control-flow model — standard-library control flow; the late-result path REUSES Day53's pydantic-backed strict validation gate (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 27 passed). Proves APPLICATION CONTROL FLOW ONLY. NOT real FastAPI/SSE wire, NOT the real OpenAI SDK/network/Provider token stream, NOT PostgreSQL/Redis/Celery, NOT integration/production. Day55 Celery, Day56 retry/backoff not implemented. No real credentials/prompts/Document content/raw Provider tokens used.

Related: [Day54 lesson](../docs/fastapi/day54-ai-streaming-client-disconnects-timeouts-and-cancellation.md) · [Day54 design/runbook](../projects/ai-backend-data-layer/api/day54-ai-streaming-client-disconnects-timeouts-and-cancellation-design.md) · [model](../projects/ai-backend-data-layer/api/day54_streaming_disconnects_timeouts_cancellation.py) · [tests](../projects/ai-backend-data-layer/api/test_day54_streaming_disconnects_timeouts_cancellation.py)

## Day55 — Celery, Worker Execution and Long-running AI Jobs

Core mental model: Celery moves messages; PostgreSQL moves truth. `Celery ACK/SUCCESS = delivery reliably handled != Job succeeded`. `broker redelivery != permission to re-call the Provider`; `Worker identity != durable Attempt identity`; `Provider timeout/OOM != proof of no execution or zero cost`; `Celery revoke != durable cancellation authority`; `configuration rollback != business-fact rollback`.

Guarded claim = the FIRST duplicate-call gate (`UPDATE jobs SET status='running',open_attempt_id=:a WHERE job_id=:j AND status IN ('queued','running') AND (lease_owner IS NULL OR lease_expiry<now) RETURNING *`): one row -> execution authority; zero rows -> STOP before the Provider call. A lease is temporary ownership; a fencing token rejects stale durable writes but cannot undo an already-issued Provider request — neither is the first gate ("根据 lease/fencing" was the reasonable-but-wrong first answer). ClaimStatus: GRANTED / CONFLICT (another live Worker -> redeliver, don't ACK) / ALREADY_TERMINAL (duplicate -> no-op ACK) / RECONCILE_ONLY (PENDING_RECONCILIATION redelivery -> reconcile from evidence, zero re-calls).

Eight identities: client_idempotency_key (one logical API command) · job_id (durable business fact) · celery_delivery_id (broker delivery occurrence) · worker_id (process) · attempt_id (durable execution attempt) · provider_request_id (external execution evidence) · provider_idempotency_key (one intended Provider call) · correlation_id (tracing/reconciliation). Redelivery/new Worker does NOT mint a new Attempt or key ("不是，可能之前的 work 又恢复了"); only an explicit, durable, authorized A2 gets a new key.

ACK timing: `early ACK -> crash silently LOSES the delivery`; `late ACK -> crash REDELIVERS, app absorbs duplicates` (safe default). ACK/`SUCCESS` = delivery handled, may be recorded by a result backend, never the business truth ("celery task success is a temporary state; durable job is a truth"). `GET /jobs/{id}` reads the PostgreSQL durable Job, NOT the Celery result backend.

Provider uncertainty / Worker loss / OOM (Out Of Memory: OS/container kills the Worker with no cleanup, so try/except alone is insufficient): persist guarded claim + Attempt + correlation + `provider_request_id` (at request open) BEFORE the call; the long Provider call stays OUTSIDE any DB transaction; unknown outcome -> `PENDING_RECONCILIATION`, reservation retained, usage never fabricated 0, NO blind re-call ("不能，成本未知"/"provider 运行未知"). A redelivered PENDING_RECONCILIATION Job -> RECONCILE_ONLY, zero Provider calls.

Poison vs transient: `transient -> bounded retry + exp backoff + jitter (Day56 depth)`; `deterministic poison -> durable classification -> quarantine/dead-letter, no ordinary requeue`. Two poison points: `envelope_version` unsupported (`job.dispatch.v2`) = can the Worker PARSE the message -> dead-letter+ACK BEFORE Job load, zero calls, Job untouched; unsupported persisted execution-contract = can the Worker EXECUTE the Job -> durable QUARANTINED+ACK AFTER Job load, zero calls. Envelope is small safe routing metadata; PostgreSQL owns state/budget/tenant/result. SUPPORTED_ENVELOPE_VERSIONS ∩ SUPPORTED_CONTRACT_VERSIONS = ∅.

Day54 cancellation in Celery: commit a durable auditable INTENT FIRST (reason/actor/timestamp/version) ("不能，因为有可能撤销失败，还需要持久化撤销意图") -> optional Celery `revoke` is best-effort AFTER the commit, never authority -> Worker cooperatively checks intent at safe points ("读取 cancellation intent"): pre-call = zero Provider calls + guarded terminal; final pre-completion = a durable intent after the last token still prevents `succeeded`. `terminal_for_intent`: user cancel -> CANCELLED, deadline -> EXPIRED. Completion vs cancellation = one guarded terminal winner (loser -> zero rows -> stop/reconcile). Crash after intent -> re-observed at-least-once, guarded transition absorbs repeats.

Outbox ordering: publish the Celery task BEFORE the `published` checkpoint ("之后写 published_at" is correct; checkpoint-first strands a queued Job with no message). Crash-between may duplicate publish (absorbed by the guarded claim); ambiguous publish outcome != success (retain/recover, accept at-least-once). Day40 boundary: reuse Day40 delivery SEMANTICS on a SUPPORTED Celery broker transport; do NOT reimplement XADD/XREADGROUP/XACK/pending-reclaim or hand-build a Celery replacement.

Graceful drain: start verified new Workers -> stop old Workers taking NEW claims -> drain in-flight within a bound -> checkpoint -> ACK -> exit (abandoned work redelivers, not lost); force-kill != business cancellation. Erroneous early-ACK release: roll the policy back FIRST (future harm only, NOT a business-fact rollback — "不能自动修复已经持久化为 running 的 job"), build the affected set from release version + a bounded time window + Worker/Attempt/Event evidence (NO bulk flip of running->queued), classify repair from evidence: `provider_request_id` present -> RECONCILE_ONLY (never blind re-dispatch); no execution evidence -> explicit guarded audited redispatch. A client idempotency key proves acceptance only, not Provider execution.

Review-round hardening (F1-F5): (F1) a lease-expiry/redelivery re-claim on an Attempt that already has a provider_request_id returns RECONCILE_ONLY and moves the Job to PENDING_RECONCILIATION — lease expiry is NOT re-authorization to call the Provider; (F2) after a guarded claim succeeds and BEFORE the Provider request, a post-claim re-check catches a cancellation intent persisted while the Job was already RUNNING (zero Provider calls, guarded terminal) — not only the QUEUED pre-claim path; (F3) `provider_request_id_recorded` is attributed to the real parent Job via a durable attempt_id->job_id path and carries attempt_id + provider_request_id + correlation_id as repair evidence (never correlation_id as a Job id); (F4) `build_affected_set` filters by release AND a bounded time window (`running_since` in [window_start, window_end]) AND running evidence, strictly excluding out-of-window/same-release running Jobs; (F5) the Outbox publishes the invariant `celery_task_id == job_id` and revoke uses that task id (`celery_task_id_for_job`), while the durable intent stays the sole business authority. P1 recovery-gap fix: a CONSERVATIVE durable marker (provider_dispatch_started_at) is persisted BEFORE the Provider request leaves the process (order: guarded claim -> marker -> Provider call -> record provider_request_id -> validate/terminal). A redelivery reconciles when the Attempt has EITHER a provider_request_id (strong evidence) OR the marker (conservative evidence); a Worker can OOM after dispatch but before recording the id, so a MISSING request id does NOT prove the Provider did not execute. Accepted safety-first false positive (marker set, request maybe not sent) -> reconcile, never retry; a provider idempotency key reduces risk but is not a reason to treat unknown external execution as a safe retry.

### Weak vs strong (Day55)
Weak: "Celery handles retries and idempotency, so redelivery is fine, and the task status tells me if the Job worked."
Strong: "The broker gives at-least-once delivery and revoke, but authority and truth live in PostgreSQL. A guarded claim decides who calls the Provider; ACK means delivery handled; an unknown outcome is PENDING_RECONCILIATION with the reservation retained and no blind re-call; cancellation is a durable intent + cooperative Worker + guarded terminal. Celery moves messages; PostgreSQL moves truth."

Schema honesty: the `cancelled`/`expired`/`pending_reconciliation`/`quarantined` statuses, a durable cancellation/expiry intent table (reason/actor/timestamp/version), per-Job `open_attempt_id`, and per-Attempt `provider_idempotency_key`/`provider_request_id`/`(schema_name,schema_version)` are new facts MODELED in-memory; a real deployment adds them via a Day48-safe FORWARD additive migration (no published Alembic revision rewritten). Day50 Job/Outbox/Relay + Day53 guarded completion/strict validation + Day54 cancellation reused.

Validation: in-memory control-flow model — standard-library control flow; the guarded completion REUSES Day53's pydantic-backed strict validation gate (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 40 passed; full api suite 388). Proves APPLICATION CONTROL FLOW ONLY. NOT a real Celery broker/Worker, NOT real ACK/redelivery/visibility-timeout, NOT Worker-loss/OOM fault injection, NOT real PostgreSQL/Redis, NOT the real Provider. Day56 retry/backoff/rate-limit/cost/backpressure and Day57 integration/failure-injection suite not implemented. No real credentials/prompts/Document content/raw Provider tokens used.

Related: [Day55 lesson](../docs/fastapi/day55-celery-worker-execution-and-long-running-ai-jobs.md) · [Day55 design/runbook](../projects/ai-backend-data-layer/api/day55-celery-worker-execution-and-long-running-ai-jobs-design.md) · [model](../projects/ai-backend-data-layer/api/day55_celery_worker_execution.py) · [tests](../projects/ai-backend-data-layer/api/test_day55_celery_worker_execution.py)

## Day56 — Provider Resilience, Rate Limits, Token Cost and Backpressure

Day55 = who may execute + no double-call on redelivery. Day56 = the admission-to-Provider control plane: even a Job holding the guarded claim needs capacity, an intact reservation, and a healthy Provider before a paid call. FOUR authorities (never interchangeable): `guarded claim` = execution authority for ONE Job (Day55, PostgreSQL); `rate permit` = fleet capacity to call NOW (shared limiter, Redis-like); `reservation` = tenant affordability (durable ledger, PostgreSQL); `circuit` = Provider-health containment (per provider/account/model/region). A claim is NOT a permit; a limiter is NOT the budget ledger.

FIVE dispatch outcomes (executable via `evaluate_dispatch`): CALL (all four agree) · DEFER (no permit / circuit OPEN / limiter outage / no reservation, and NO call made — persist next_attempt_at + reason + defer_count + deadline, release Worker, NO sleep) · RECONCILE (external call may have executed / UNKNOWN, or Attempt evidence — never blind retry) · TERMINAL (durable cancel/deadline intent -> guarded CANCELLED/EXPIRED) · NOOP (already terminal). Order: terminal/NOOP -> durable intent -> execution evidence -> deadline -> circuit -> permit -> reservation -> CALL. Facts OUTRANK capacity retry.

Retry storm != cache avalanche: synchronized 429 retries re-amplify the dependency (thundering herd); cache avalanche is cache expiry loading the backend ("不应该会导致缓存雪崩" saw the amplification, wrong term). Fix: bounded exponential backoff + FULL jitter; `Retry-After` is an EARLIEST floor, not permission for all Workers to wake together (`compute_next_attempt_at` = max(jittered backoff, Retry-After floor)).

No-permit-before-call = durable DEFER ("是一个可恢复的等待容量/延迟重试状态"), NOT FAILED / NOT PENDING_RECONCILIATION (nothing external happened). A defer consumes NO execution_retry_count; it uses a separate bounded defer_count + deadline; next_attempt_at is never past the business deadline. Limiter OUTAGE -> fail CLOSED for new paid calls by default ("继续调用provider" was wrong: losing the only cross-Worker bound means a burst melts the Provider); reads/cancel/completed-reads/reconcile still work; emergency fail-open is an EXPLICIT bounded policy only.

Cost: reserve the BOUNDED WORST-CASE cost from the persisted contract (`max_tokens/1000 * price`) at acceptance, NOT the remaining balance ("500 token" corrected); if worst case can't be covered, do NOT call. Success -> settle actual use + RELEASE unused money to the durable TENANT ledger, NOT the limiter ("应该回归到limiter" corrected — capacity != money). Unknown execution -> hold reservation for reconciliation (never zero it).

Backpressure BEFORE the durable Job + Outbox commit ("创建 Job 之前拒绝/限速"): tenant over its own quota -> 429; system-wide capacity/dependency unavailable -> 503 (system dominates); never 202 for a commitment you can't keep; an accepted Job is NEVER retro-429/503. Degradation: a Worker never silently reduces persisted `model`/`max_tokens` ("不能，worker只是执行者"); allowed only if the persisted product-authorized contract permits it, down to a floor (`min_model`/`min_max_tokens`).

429 by execution certainty (not status code alone): Adapter classifies DEFINITELY_NOT_ACCEPTED (safe ordinary-defer/retry) vs MAY_HAVE_EXECUTED / UNKNOWN (RECONCILE). A recorded provider_request_id -> MAY_HAVE_EXECUTED; a bare 429 -> UNKNOWN; only `accepted_header=False` + no request id -> DEFINITELY_NOT_ACCEPTED. Any Attempt evidence (request_id or the Day55 conservative dispatch marker) forces RECONCILE before capacity gating. Circuit: CLOSED allows, OPEN durably defers new calls ("暂时停止向该 Provider 发起新的调用"), HALF_OPEN allows a small bounded PROGRESSIVE probe set — one probe success does NOT close the circuit or release the herd ("不能，应该少量的受控渐进恢复"). Key = `circuit:{provider}:{account}:{model}:{region}`, no secrets.

Cancellation/terminal OUTRANK a claim ("claim 先到先得" but corrected: claim elects a decision-maker, it doesn't override a durable cancellation intent); re-check cancel/budget/contract/circuit/capacity when a deferred Job wakes. Terminal facts -> NOOP; unknown execution / Provider evidence -> RECONCILE. Deadline expiry: guarded EXPIRED + reservation RELEASE only with proof of NO external execution; any evidence -> PENDING_RECONCILIATION + reservation HELD.

Zero-defer incident (bad release set max defer = 0, prematurely expiring capacity-deferred Jobs): step 1 rollback the config to stop FUTURE harm ("第一步回滚错误配置") — NOT a business-fact rollback; step 2 repair persisted Jobs. Build a BOUNDED affected set from release + time window + expiry reason + Attempt/Event evidence + deadline; preserve expired history, never bulk-flip to queued. Re-dispatch ONLY Jobs with proof of no Provider execution AND still-valid contract/deadline/budget, via a guarded audited repair that writes a NEW durable Outbox dispatch intent for the Relay ("写入一个新的 durable Outbox dispatch intent 再由 Relay 发布") — never a direct queue call; Jobs with Provider evidence are RECONCILE_ONLY.

Review-round P1 fixes: (P1-1) `compute_next_attempt_at` keeps Retry-After as an EARLIEST floor but adds bounded jitter ABOVE it — result always >= floor, different draws differ, so no wake-all. (P1-2) a HALF_OPEN probe slot is taken via `allow_probe` ONLY at an actual CALL (the gate reads `has_probe_capacity`), so a Job that reaches HALF_OPEN then DEFERs (no capacity / limiter outage / missing reservation) never leaks a slot or strands the circuit; a no-call is not a probe failure. (P1-3) `worst_case_cost` = bounded INPUT cost + bounded OUTPUT cost (separate unit prices), not output-only; `settle_actual` returns SETTLED or, when actual>reserved, OVERAGE_RECONCILE — it charges only the reserved amount, records `cost_overage`, and enters RECONCILIATION_PENDING (never silently overdraws the tenant); `reserve_worst_case` is idempotent. (P1-4) `repair_redispatch` is a guarded idempotent atomic decision: a stable `repair_id` (`repair:{job}:{release}:{reason}`) yields exactly ONE Outbox intent even under duplicate/concurrent repair (ALREADY_APPLIED thereafter); it re-verifies affected-set membership, EXPIRED status, no cancellation intent, deadline, no Provider evidence, and a fresh worst-case reservation, preserving the EXPIRED history in an audited `repair_history` (no unaudited bulk flip); Provider-evidence Jobs stay RECONCILE_ONLY.

Review-round concurrency P1 fixes: (P1-1) HALF_OPEN probe acquisition is now the ATOMIC lock-guarded `try_acquire_probe` at CALL time (the read-only `has_probe_capacity` is only a cheap early-out); two racing Workers can never both probe past `half_open_max_probes`, and the loser RELEASES its rate permit and DEFERs (no permit leak). (P1-2) `repair_redispatch` runs its repair-id claim + eligibility rechecks + reservation + audit + status change + single Outbox intent inside ONE lock-guarded critical section, so two concurrent repairs of the same id yield exactly one REDISPATCHED + one ALREADY_APPLIED, one Outbox intent, one reservation. In-memory locks model the atomic boundary (a real system uses DB row locks / INSERT ... ON CONFLICT / SELECT ... FOR UPDATE, or Redis Lua); verified with threading.Barrier tests — this is in-memory concurrency, NOT PostgreSQL isolation / real Redis / Celery / production.

Budget concurrency fix: `TenantBudgetLedger` now runs every reservation/balance op (reserve_worst_case, has_reservation, settle_actual, release_reservation, hold_for_reconciliation, available, can_afford) under a ledger-level lock, so the affordability check + balance deduction + reservation write are ONE atomic critical section — two Jobs racing a tenant whose balance covers only one can never both reserve and overspend; reserve_worst_case is idempotent per job_id (no double-charge). In-memory lock models the atomic boundary (real: UPDATE ... WHERE available - reserved >= :amt RETURNING / SELECT ... FOR UPDATE); threading.Barrier tests — in-memory concurrency only, NOT PostgreSQL isolation / Redis / Celery / production. The in-memory artifact now exercises concurrency control flow for the rate permit, the HALF_OPEN probe, repair idempotency, AND the budget reservation.

CircuitBreaker concurrent-state fix: one threading.RLock now guards ALL per-failure-domain state (_state, _fails, _probes_in_flight, _probe_successes), so every read-modify-write is atomic — concurrent record_failure never loses a count (the circuit reliably OPENs at the threshold) and concurrent HALF_OPEN probe success/failure never lose an in-flight decrement or overwrite a state transition. RLock (reentrant) lets a locked method call another locked method (e.g. state) without deadlock; has_probe_capacity stays a hint, try_acquire_probe stays the authoritative atomic acquire, the probe loser still releases its rate permit and DEFERs, and OPEN/HALF_OPEN/CLOSED progressive recovery is unchanged. In-memory threading tests only — NOT Redis Lua / PostgreSQL isolation / Celery / production.

CircuitBreaker late-success rule: because several HALF_OPEN probes can be in flight, record_probe_success only counts toward progressive recovery (and may CLOSE) when the domain is STILL HALF_OPEN. A LATE success that returns after another probe already failed and re-OPENed the circuit safely releases its in-flight slot but does NOT count, does NOT flip the known failure back to CLOSED, and (being uncounted) does NOT carry into the next HALF_OPEN round — a failed probe latches OPEN until an explicit new recovery round. HALF_OPEN-fail-reopens, try_acquire_probe as the sole atomic acquire, and progressive multi-success close are unchanged. In-memory threading tests only.

### Weak vs strong (Day56)
Weak: "Retry on 429 with backoff, and if the limiter is down keep calling so we don't block."
Strong: "Backoff with jitter and Retry-After as a floor; classify the 429 by execution certainty; if the shared limiter is down I fail closed for new paid calls because I lost the only fleet-concurrency bound. No permit is a durable defer, not a failure; unknown execution is reconciliation, not a retry. A claim is execution authority, a permit is capacity, a reservation is money, a circuit is health."

Schema honesty: a `deferred` status, a durable defer record (retry_reason/next_attempt_at/defer_count/deadline), execution_retry_count vs defer_count, and a tenant cost-reservation ledger are new facts MODELED in-memory; a real deployment adds them via a Day48-safe FORWARD additive migration. Rate limiter + circuit state are TRANSIENT coordination (Redis-like), not durable tenant truth. Day55 guarded claim/Outbox/P1 marker + Day54 durable intents reused.

Validation: in-memory control-flow model — standard-library only, imports Day54 IntentKind (Python 3.10.12, pytest 7.4.3 -> 54 passed; full api suite 442). Proves APPLICATION CONTROL FLOW ONLY. NOT a real Celery broker/Worker, NOT a real Redis distributed limiter/circuit, NOT real PostgreSQL, NOT real Provider traffic/rate limits/costs, NOT load, NOT Worker-kill fault injection, NOT production. Day57 integration/failure-injection and Day58 observability not implemented. No real credentials/prompts/Document content/raw Provider payloads/secrets used.

Related: [Day56 lesson](../docs/fastapi/day56-provider-resilience-rate-limits-token-cost-and-backpressure.md) · [Day56 design/runbook](../projects/ai-backend-data-layer/api/day56-provider-resilience-rate-limits-token-cost-and-backpressure-design.md) · [model](../projects/ai-backend-data-layer/api/day56_provider_resilience.py) · [tests](../projects/ai-backend-data-layer/api/test_day56_provider_resilience.py)

## Day57 — AI Backend Testing, Fake Providers, Contract Tests and Failure Injection

Day56 = the policies (guarded claim / rate permit / reservation / circuit -> CALL/DEFER/RECONCILE/TERMINAL/NOOP). Day57 = turn those policies into REPEATABLE EVIDENCE with deterministic Fake Providers, Adapter contracts, and failure injection — driving the REAL Day56 functions + Day53's real validator, not re-implementing them.

Test the side effects, not just the status: a bare Provider 429 -> durable `PENDING_RECONCILIATION` AND assert the Provider call count stays ONE and no ordinary retry got a new rate permit, reservation HELD, redelivery reconcile-only ("持久化数据库事实应该是 pending_conciliation" -> normalized PENDING_RECONCILIATION). Unknown external execution is not safe retry.

Fake Provider != integration test. A ControllableFakeProvider (scripted outcomes, independent call log that survives "Worker loss", request_received/release_response gates via threading.Event, execution-certainty evidence) proves deterministic APPLICATION semantics fast; only real PostgreSQL/broker/Worker/Redis integration proves transactions, redelivery, process loss, and shared coordination. Keep FOUR evidence tiers everywhere: CONCEPTUAL/STATIC, EXECUTED LOCAL RUNTIME, INTEGRATION RUNTIME, PRODUCTION. Real PostgreSQL/Celery/Redis are INTEGRATION RUNTIME (currently NOT RUN, NOT "production"); real Provider traffic + production validation are PRODUCTION (NOT RUN); an in-process double is EXECUTED LOCAL RUNTIME, never integration.

Missing `provider_request_id` != no execution: a Worker can crash after the request leaves the process and before it persists the id; Day55's conservative `provider_dispatch_started_at` marker forces RECONCILE in that window. A provider idempotency key reduces risk but is not proof of execution and not permission to retry. The Adapter must POSITIVELY classify DEFINITELY_NOT_ACCEPTED before an ordinary retry; otherwise UNKNOWN/MAY_HAVE_EXECUTED reconcile.

Adapter contract tests assert the application-owned typed outcome (failure kind, execution certainty, optional request id, safe retry info, safe metadata) — NOT raw SDK exception classes, HTTP codes, or private SDK fields; the Adapter never writes Job state or cost. Schema-contract: a syntactically valid Provider JSON that violates the persisted (schema_name, schema_version) is a CONTRACT_VIOLATION (Day53 real validator), not business success — no Result Artifact, not succeeded, no blind second call. Current Provider config governs NEW calls only; the persisted contract governs result acceptance.

Determinism: inject a FakeClock + a scripted DeterministicRandom into backoff/jitter tests; assert Retry-After is an EARLIEST floor, every wake >= floor, controlled draws spread — never assert a wake-all at the exact Retry-After. Controlled gates (asyncio.Event / threading.Event) open timeout/kill windows without sleeps. A timeout AFTER the Fake Provider records receipt is not proof of no execution -> PENDING_RECONCILIATION + reservation HELD.

Late result completes ONLY if the Job is non-terminal AND awaiting reconciliation AND the payload strictly validates against the bound schema AND job_id + attempt_id + correlation_id + provider_request_id all match durable evidence (missing durable id == mismatch); a terminal CANCELLED Job rejects even a fully matching late result without overwriting state. Cancellation-vs-completion needs a barrier/failpoint over REAL DB concurrency: exactly one guarded terminal transition wins, the loser sees zero rows.

Limiter outage fails closed for new paid calls: Provider calls zero, Jobs durably DEFERRED (reason + bounded next_attempt_at + separate defer_count), Worker slots released, execution_retry_count unchanged; on wake re-evaluate ALL gates and avoid a retry storm. Backoff never extends an accepted Job past its deadline: no evidence -> guarded EXPIRED + reservation release; marker/request evidence -> PENDING_RECONCILIATION + reservation held. Admission backpressure is tested BEFORE the durable commitment: system-unavailable -> 503 (commits no Job/Outbox/reservation/call); system-wide 503 dominates tenant 429.

Bad-release drill: a release that classified every bare 429 as definitely-not-accepted -> FIRST rollback the mapping (contain future harm), THEN build a bounded affected set (release version + bounded time window + incident reason + Attempt/defer/Event evidence). Do NOT bulk-flip EXPIRED to QUEUED. provider_request_id or dispatch marker -> RECONCILE_ONLY. Only proven-no-execution Jobs with valid contract/deadline/budget and no cancellation intent get guarded, audited repair via ONE new Outbox intent. Repair is a durable decision, not an Attempt identity: a unique `repair:{job_id}:{release_version}:defer_deadline_expired` claimed atomically -> duplicate/concurrent repair gets ALREADY_APPLIED (no second reservation, no second Outbox intent). Transport is at-least-once; guarded execution stops duplicate delivery from becoming duplicate Provider work.

Runtime evidence: `pytest passed` alone is NOT audit evidence. Preserve exact command + revision/config, precise fault point, committed-DB queries via a NEW connection, Fake Provider cross-process call log, and broker delivery/Worker lifecycle evidence. Repair audit stores only safe decision evidence (IDs, release/reason/policy, safe classification, timestamps, evidence presence) — never raw prompt, raw Provider payload, or secrets; a forensic raw-evidence store is a separate minimized/redacted/encrypted system. A real `job_repair_history` table + migration is forward-additive DESIGN only, not yet implemented — do not claim it exists.

### Weak vs strong (Day57)
Weak: "The Provider timed out, so retry it; the tests pass, so recovery works."
Strong: "A timeout is unknown execution: reconcile with the reservation held, don't retry, and prove the call count stayed one. A passing fake test is application-level evidence only — real PostgreSQL/broker/Worker/Redis integration is a separate tier I mark NOT RUN until it actually runs."

Validation: deterministic in-memory verification harness driving Day56 functions + Day53's real pydantic validator (Python 3.10.12, pydantic 2.5.0, pytest 7.4.3 -> 23 passed; full api suite 465). Proves EXECUTED LOCAL RUNTIME application state-machine / Adapter-contract / failure-injection control flow ONLY. NOT real PostgreSQL transaction/rollback/isolation, NOT real Celery broker redelivery, NOT real Worker-kill, NOT a real Redis limiter/circuit, NOT real Provider traffic — all NOT RUN (see VALIDATION_MATRIX). Day58 observability is not implemented. No secrets/raw prompts/raw Provider payloads used.

Related: [Day57 lesson](../docs/fastapi/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection.md) · [Day57 design/runbook](../projects/ai-backend-data-layer/api/day57-ai-backend-testing-fake-providers-contract-tests-and-failure-injection-design.md) · [harness](../projects/ai-backend-data-layer/api/day57_testing_harness.py) · [tests](../projects/ai-backend-data-layer/api/test_day57_testing_harness.py)

## Day58 — Production AI API Capstone, Observability and English Interview

Phase 4 capstone. Day57 tested the reliability rules; Day58 makes distributed execution EXPLAINABLE + AUDITABLE across API -> Outbox Relay -> Worker Attempt -> Provider Adapter -> completion/reconciliation, while PostgreSQL stays the source of business truth. Core principle: observability is a correlated, safe, aggregatable, reviewable EVIDENCE system AROUND durable state — it does NOT replace the durable state machine and does NOT grant permission to retry unknown external work. Missing telemetry = observability GAP, never proof of no execution.

Five identities, TWO separate contexts: `IdentityLifecycle` = a durable Worker Attempt context (job_id+correlation_id STABLE; attempt_id+trace_id per Attempt; NO request_id; new_attempt() mints new attempt_id+trace_id). `HttpRequestContext` = one inbound HTTP request (job_id+correlation_id + a NEW request_id AND a NEW trace_id; NO attempt_id) via http_request()/start_http_request(). A status/poll HTTP request does NOT inherit or silently reuse a Worker Attempt's attempt_id/trace_id; legit distributed-trace continuity is an EXPLICIT parent_trace (traceparent link), never silent reuse. Correlation != identical lifecycle ("all ids unchanged across retry" was the reasonable-but-wrong first answer).

Structured events (safe fields only — event_name, job_id, correlation_id, attempt_id, trace_id, provider, model, outcome, bounded duration_ms, request_id_present, dispatch_marker_present, reason): NEVER raw prompts, raw Provider responses, api_key, secrets, tenant documents (StructuredEvent raises UnsafeTelemetryError). `provider.call.timeout` = the app's OBSERVED timeout/unknown outcome, NOT proof of non-execution. `provider.call.suppressed` = a later reconciliation Attempt refused a second Provider call because durable evidence forbids it; reason=`prior_attempt_may_have_executed`, dispatch_marker_present=True. The StructuredEvent extra field may never shadow a canonical field, and safety does NOT rely on caller discipline: every canonical VALUE is validated — ids/event_name have bounded shapes (no secrets/newlines), provider/model/outcome from controlled allowlists/registry, duration_ms a bounded non-negative int, and reason a FINITE enum (e.g. prior_attempt_may_have_executed) NOT free text; a raw prompt/response/api key/bearer token/overlong value in any canonical field (reason/provider/id) is rejected (UnsafeTelemetryError). Prompt/output minimization is a tenant-data/privacy boundary, not a logging preference.

Metrics + cardinality: Counter `provider_call_total{provider,model,outcome}` — query its RATE, not the raw cumulative total; Histogram `provider_call_duration_seconds{provider,model}` — distribution/tail latency, not just average; Gauge `provider_calls_in_flight{provider,model}` — rises at call start, falls at completion/timeout ("Counter" was corrected to Gauge); Gauge `jobs_pending_reconciliation{provider,model}` — backlog rises/falls. job_id/attempt_id/trace_id belong in logs/traces, NEVER in metric labels (MetricSpec raises HighCardinalityLabelError). Low cardinality requires controlled NAMES and VALUES: provider/outcome from a controlled allowlist, and model from a FINITE controlled registry (ALLOWED_MODEL_VALUES) — a regex alone allows unbounded distinct models, so unknown/user model aliases are normalized to a bounded bucket (normalize_model_label -> __other__) before labeling; validate_label_values raises LabelValueError otherwise. Never label with a deployment URL or raw user input. Alert on a COMBINATION — timeout rate + in-flight saturation + sustained reconciliation backlog — so one transient timeout doesn't page.

Traces + async causality (OpenTelemetry vendor-neutral): API acceptance, Relay, Worker Attempt A, later Attempt B are SEPARATE traces across durable async boundaries. A Provider Adapter call is a CHILD span of the current Attempt trace (shares trace_id). Later async work uses a SPAN LINK (trace_id+span_id context) to the IMMEDIATE preceding causal trace — not a child of an already-ended HTTP span, not fake synchronous nesting. Link only the immediate prior by default; job_id+correlation_id carry stable end-to-end continuity; do NOT fan every retry out to every historical trace.

Durable truth outranks telemetry: `provider_dispatch_started_at` persisted BEFORE the external call; a missing provider_request_id or missing telemetry is NOT proof no call happened. PostgreSQL Job/Attempt/marker/reservation facts determine retry/reconciliation safety; logs/traces/metrics explain and help prove but never AUTHORIZE a repeat Provider call. Telemetry exporter outage (default): keep core processing, never turn an accepted Job into FAILED or permit unsafe retry; bounded buffering then drop; expose health via telemetry_export_failures_total / telemetry_events_dropped_total / telemetry_export_queue_depth; on recovery, recover() drains the buffered events (FIFO) to an observable sink and resets queue depth to 0 (already-dropped events stay dropped). A stricter regulatory/product availability trade-off must be an EXPLICIT policy, never an accidental exporter-failure side effect.

Bad-observability-release rollback drill (release removed attempt_id from Worker logs + added job_id to provider_call_total labels): FIRST rollback the observability release/config to stop further correlation loss + high-cardinality damage (config only). Do NOT roll back/overwrite valid Job/Attempt/dispatch-marker/reservation/Outbox facts — this is an observability failure, not a business-state failure. Bound the affected set by release version + time window; reconstruct affected Jobs from durable PostgreSQL facts; MARK telemetry gaps honestly (never fabricate missing logs/traces). A PENDING_RECONCILIATION Job with incomplete telemetry but a durable dispatch marker (or provider_request_id) stays RECONCILE_ONLY — never an ordinary requeue. ABSENCE of a marker/request id is NOT proof of no execution (Day57): an ordinary requeue needs a POSITIVE DEFINITELY_NOT_ACCEPTED execution certainty (Day56), and even then Day58 does not requeue itself — classify_observability_recovery returns ELIGIBLE_FOR_GUARDED_RECOVERY, handing the Job to Day56's existing guarded recovery (contract/deadline/budget/cancel re-check); UNKNOWN/MAY_HAVE_EXECUTED/missing certainty stay RECONCILE_ONLY.

Evidence tiers (four): CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME (in-process deterministic model, this artifact) / INTEGRATION_RUNTIME (real FastAPI+OpenTelemetry exporter, real PostgreSQL/Redis/Celery — NOT RUN) / PRODUCTION (real Provider traffic — NOT RUN). A reviewable runtime-evidence pack needs: scenario + expected outcome; exact command/revision/config/time window; fault point; logs/traces/metrics; committed DB queries from a NEW connection; independent Provider call evidence; Worker/Relay/broker lifecycle; actual result; explicit tier + NOT RUN limits. `pytest passed` alone is not a reviewable evidence pack.

### Weak vs strong (Day58)
Weak: "Add job_id to every metric and log so we can slice per Job; if telemetry is down, fail the jobs so we don't lose data."
Strong: "Keep job_id/attempt_id/trace_id in logs and traces, not metric labels, to avoid a cardinality blowup. If the exporter is down, keep core processing and never fail an accepted Job — telemetry is evidence around durable state, not a retry authority. Durable PostgreSQL facts, not telemetry, decide reconciliation."

Validation: in-process deterministic observability model (Python 3.10.12, pytest 7.4.3 -> 37 passed; full api suite 502); imports Day57 EvidenceTier + Day56 ExecutionCertainty. Proves EXECUTED_LOCAL_RUNTIME identity/event/metric/trace/telemetry-policy/rollback control flow ONLY. NOT RUN: real FastAPI runtime + OpenTelemetry exporter, real PostgreSQL/Redis/Celery integration, real Provider traffic/production (INTEGRATION_RUNTIME + PRODUCTION per VALIDATION_MATRIX_DAY58). No secrets/raw prompts/raw Provider responses/tenant documents used.

Related: [Day58 lesson](../docs/fastapi/day58-production-ai-api-capstone-observability-and-english-interview.md) · [Day58 design/runbook](../projects/ai-backend-data-layer/api/day58-production-ai-api-capstone-observability-and-english-interview-design.md) · [model](../projects/ai-backend-data-layer/api/day58_observability_capstone.py) · [tests](../projects/ai-backend-data-layer/api/test_day58_observability_capstone.py)

## Day59 — Real FastAPI Runtime, PostgreSQL and Alembic Integration

Acceptance boundary: a `202`, a log line, a live SQLAlchemy `Session`, or a reservation is NOT proof of acceptance. A new Job earns `202` only after ONE short transaction commits a queued Job + persisted `request_fingerprint` + exactly ONE `job.dispatch_requested` Outbox intent + Job–Document link(s). Verify committed state from a NEW connection (a live Session can serve uncommitted identity-map rows). The HTTP transaction NEVER calls a Broker/Worker/Provider/Object Storage — it persists the Outbox intent for a later Relay (Day60).

Idempotency: `UNIQUE(tenant_id, idempotency_key)` is the physical dedup; the durable `job_id` is the accepted fact. The `Idempotency-Key` travels in the HTTP header (Day43; missing/blank → `400` before any write) and is the command dedup key — NOT part of the fingerprint (Day50). `request_fingerprint = SHA-256(ordered document_ids + normalized business_input)` (the behavior-relevant command) separates an exact retry from the same key reused for a different request, so same key + different Document → `409`. Same tenant/key/fingerprint → return the first Job; same key + different fingerprint → `409`; fresh key + unverified/wrong-tenant Document → `422` with NO acceptance facts. The route is ONE `session.begin()` using `INSERT ... ON CONFLICT (tenant_id, idempotency_key) DO NOTHING RETURNING` (create-or-return, not SELECT-then-INSERT); on no-row it re-reads the existing fingerprint (replay vs 409, never swallowing an unrelated error). Document verification joins `app.documents` to `app.upload_sessions` on `session_status='verified'` (there is no `documents.verified_at`). Document input ORDER is a durable fact: each `app.job_documents` row is written with `document_role='input'` and `input_order=1..n` in the client's order (no `set()`/`dict.fromkeys()`), so a Worker can reconstruct the sequence. Duplicate `document_ids` are a malformed command (PK collision + ambiguous order) -> `422` BEFORE the transaction (no Job/Outbox/links). Idempotency is checked BEFORE revalidating mutable Document state, so an exact retry returns the original Job even if the object later became unavailable.

Document lifecycle: verified = acceptance-time metadata/provenance + object verification succeeded; it does NOT guarantee future Object Storage readability. A later Worker handles unavailable bytes via an explicit recovery/failure path and NEVER retargets an accepted Job to a newly uploaded Document. New input = new upload/verification, new key, new Job.

Readiness vs liveness: `/livez` = process up. `/readyz` = DB reachable AND schema at the expected Alembic revision (`0008_day59_acceptance`); a ready process on the wrong revision returns `503`, not silent acceptance. A DB failure is a readiness `503`, not a blanket `500`.

Migrations: raw Day42 baseline → Alembic `stamp 0001_baseline` → controlled upgrade. Real failures diagnosed in class: Python 3.9 fails on 3.10+ `X | Y` unions (require 3.10+); a blank DB needs the raw baseline + stamp first; `alembic_version.version_num varchar(32)` can't hold the 33-char `0007_merge_reconciliation_polling` (upgrade rolls back — inspect the final committed revision from a fresh connection). Fix: a controlled ONLINE-only `env.py` repair widens the version column to `varchar(128)` only when it exists and is too small (never in FastAPI, never touching app data). `0008` is ADDITIVE (nullable `request_fingerprint` + SHA-256-shape CHECK + partial unique index for one dispatch intent per Job), so an API rollback is normally safer than an immediate Alembic downgrade; prefer a later forward migration for repairs.

Local identity seam: `X-Integration-Tenant` is honored ONLY when `DAY59_INTEGRATION_TEST=1` AND the DB host is loopback. It is a constrained integration-test seam, NEVER a client-supplied production tenant authority (that would break tenant isolation). Production identity stays Day51 JWT + Day52 active-membership/role authorization. Docker `--rm` deletes writable-layer data at stop (chosen for disposable local integration); named volumes/external DBs persist.

Evidence tiers: CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION. Executed in class (disposable local): Python 3.11 compile; real Uvicorn + PostgreSQL 16 container; raw baseline → stamp → upgrade through `0008`; readiness with matching revision (wrong revision → 503); atomic acceptance (independent Job=1/dispatch=1/link=1); exact replay; different-payload 409; invalid-Document 422 with independent 0/0/0; two concurrent same-key requests with independent 1/1/1. After the Day59 review fixes (autobegin/ON CONFLICT, real `session_status='verified'` verification, `Idempotency-Key` header, fingerprint over documents, conflict re-read) the corrected acceptance path was NOT re-run against real PostgreSQL — INTEGRATION_RUNTIME NOT RERUN. The repository agent re-ran only `py_compile` + the stdlib `test_day59_acceptance_logic.py` (12 passed, EXECUTED_LOCAL_RUNTIME pure decision logic). NOT RUN: real Redis/Celery broker/Relay/Worker, worker kill/redelivery, real Object Storage/presigned/checksum, real Provider HTTP/cost, real OpenTelemetry exporter, real JWT/JWKS/secret manager, production migration lock/load/zero-downtime, multi-replica, load testing, production validation. `pytest passed` never auto-upgrades to INTEGRATION_RUNTIME/PRODUCTION. No secrets, local URLs/passwords, tokens, or tenant fixture values are committed.

Related: [Day59 lesson](../docs/fastapi/day59-real-fastapi-runtime-postgresql-and-alembic-integration.md) · [Day59 design/runbook](../projects/ai-backend-data-layer/api/day59-real-fastapi-runtime-postgresql-and-alembic-integration-design.md) · [runtime app](../projects/ai-backend-data-layer/api/day59_runtime_app.py) · [acceptance logic](../projects/ai-backend-data-layer/api/day59_acceptance_logic.py) · [tests](../projects/ai-backend-data-layer/api/test_day59_acceptance_logic.py) · [0008 migration](../projects/ai-backend-data-layer/api/day48_alembic/versions/0008_day59_acceptance.py)

## Day60 — Outbox, Redis/Celery Broker and Worker Recovery Integration

Relay ordering: publish to the Broker FIRST, then guarded-checkpoint `published_at` under the fencing token. A crash between them leaves `published_at IS NULL` → retry redelivers → at-least-once. `published_at` is a DELIVERY checkpoint, never proof of execution/success; `published_at IS NULL` proves only "no Relay checkpoint" (execution truth = Job/Attempt/Event, and Day61 Provider/Result). Competing Relays: `SELECT ... FOR UPDATE SKIP LOCKED` + `relay_owner`/`relay_token`/`relay_claim_expiry` (0009 columns); NEVER hold the DB lock across Broker I/O — publish outside the lock, fenced checkpoint under the token.

Worker authority (delivery ≠ execution authority): `UPDATE app.jobs SET job_status='running', lease_owner, lease_expiry WHERE job_status='queued' RETURNING` = exactly one winner; it creates Attempt/Event facts and completes only under the matching lease token, so a stale Worker cannot commit after a takeover. Celery: `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`; ACK is TRANSPORT acknowledgement AFTER processing, not a business-state commit.

Duplicate/redelivery/expiry: duplicate while THIS worker holds a credibly active lease → NOOP (no Provider call, no 2nd claim); redelivery to a DIFFERENT worker while the lease is still unexpired → DEFER to the durable PostgreSQL sweep (worker-loss only SUSPECTED, don't seize); expired lease + external evidence (`provider_request_id` OR Day55 `provider_dispatch_started_at`) → RECONCILE_ONLY / `PENDING_RECONCILIATION` (never a 2nd call); expired lease + NO evidence → the sweeper redispatches. Celery retry is transport, NOT recovery authority.

Recovery sweep: expired + evidence → RECONCILE_ONLY; expired + none → atomically `running -> queued`, record a recovery audit event, write EXACTLY ONE new `job.redispatch_requested` Outbox intent; Relay delivers it. Durable recovery authority = PostgreSQL state + a newly committed Outbox intent.

Bounded early-ACK repair: contain by rolling back the erroneous CONFIG first. Repair NEVER calls `.delay()` (immediate `apply_async()` publish; no transactional/replayable/auditable intent). Select a BOUNDED eligible set (bad release + time window + `queued` + original dispatch checkpointed + no attempts/evidence + no conflict + valid deadline/contract/budget + not-already-applied), re-verify in the repair tx, record immutable `app.job_repair_history` keyed by deterministic `repair_id=repair:{job_id}:{release_version}:{reason}` (PK ⇒ idempotent under concurrency), write one new redispatch intent before commit.

Real runtime `day60_delivery_runtime.py`: `OutboxRelay` (FOR UPDATE SKIP LOCKED claim, publish OUTSIDE the lock, fenced `published_at` checkpoint), `run_worker_attempt` (guarded queued→running claim + Attempt/Event + lease-token guarded completion; a stale Worker cannot commit), `recovery_sweep` (ONLY expired `running`: evidence→`pending_reconciliation`, else `running→queued` + audit + ONE `job.redispatch_requested` intent), `repair_early_ack` (release-filtered, re-verify, immutable `job_repair_history` linked to ONE redispatch intent; never `.delay()`/`apply_async()`). The lease is the EXISTING Day48 TRIPLE `lease_owner`/`lease_token`/`lease_expires_at` (constraints `jobs_lease_triple_coherent` + `jobs_running_requires_lease`); the guarded claim writes all three atomically and completion matches `lease_token` (not owner). Shared boundary: `lease_expires_at > now` = active, `<= now` = expired (incl `== now`). Real Celery app `day60_celery_app.py` (acks_late/reject_on_worker_lost/prefetch1 + `execute_job_attempt` task) with Relay/sweeper entrypoints `day60_relay.py`/`day60_sweeper.py` — ONLY the Relay publishes (`apply_async`); recovery/repair only write durable Outbox intents. Repair is release-filtered + incident-time-windowed (`in_time_window`, never hardcoded True) + caller-attested (no-conflict/deadline-contract-budget are explicit auditable attestations, else conservatively refused). Repair persists the operator's bounded-eligibility decision to `job_repair_history` (`incident_start`/`incident_end`/`no_conflict_attested`/`deadline_contract_budget_valid_attested`, added by `0012_day60_repair_audit_attestation`, written in the repair tx). On `IntegrityError` the repair RE-READS the committed `repair_id` row in a fresh tx: `already_applied` ONLY for a matching same-repair duplicate (job_id/release/reason + linked Outbox), else `repair_failed` (an unrelated UNIQUE/FK violation is never faked as success). Migrations: `0009`/`0010`/`0012` additive; `0011_day60_lease_realign` is a CONTROLLED CORRECTIVE DROP of the never-written `lease_expiry` (NOT additive/expand-only/zero-downtime; production would keep the col, stop rw, multi-stage remove). App-factory `create_app(expected_revision='0012_day60_repair_audit_attestation')`.

Evidence tiers: CONCEPTUAL_STATIC / EXECUTED_LOCAL_RUNTIME / INTEGRATION_RUNTIME / PRODUCTION. The repository has a REAL Relay/Worker/recovery/repair runtime on the EXISTING lease triple + the `0011` schema realign; the updating agent executed ONLY `py_compile` + the stdlib `test_day60_delivery_recovery_logic.py` + `test_day60_runtime_schema_contract.py` (26 passed, EXECUTED_LOCAL_RUNTIME pure-logic + static-contract incl. sweep negatives, lease boundary, in_time_window, release/window/attestation repair rejects, full-lease-triple SQL shape, repair audit-column persistence, and the IntegrityError duplicate-vs-repair_failed classification). Count: 34 passed. It has no Docker/PostgreSQL/Redis, so the real runtime was NOT executed against a real DB+broker — INTEGRATION_RUNTIME NOT RERUN; no integration result is claimed. Required rerun matrix (in the runbook): Relay crash after-publish/before-checkpoint → redelivered but one valid completion; Worker-kill → no double-execute, sweep→one redispatch→new Attempt completes; expired+evidence → `pending_reconciliation`, no 2nd call; concurrent repair → one audit + one intent; queued/terminal never swept. NOT RUN: real Provider HTTP/request-ids/cost, Object Storage Result Artifact, OpenTelemetry (Day61); production load/security/zero-downtime/scheduling; multi-replica. `pytest passed` never auto-upgrades to INTEGRATION_RUNTIME/PRODUCTION. No secrets, local URLs/passwords/tokens/fixture ids committed.

Related: [Day60 lesson](../docs/fastapi/day60-outbox-redis-celery-broker-and-worker-recovery-integration.md) · [Day60 design/runbook](../projects/ai-backend-data-layer/api/day60-outbox-redis-celery-broker-and-worker-recovery-integration-design.md) · [delivery/recovery logic](../projects/ai-backend-data-layer/api/day60_delivery_recovery_logic.py) · [app-factory](../projects/ai-backend-data-layer/api/day60_runtime_app.py) · [tests](../projects/ai-backend-data-layer/api/test_day60_delivery_recovery_logic.py) · [0009 migration](../projects/ai-backend-data-layer/api/day48_alembic/versions/0009_day60_delivery_runtime.py)

## Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence

External-call checkpoints: a Provider HTTP timeout does NOT prove non-execution — never blind-retry a billable call. Persist `provider_dispatch_started_at` BEFORE the call (pre-call marker, not success); persist `provider_request_id` as soon as returned and BEFORE the Artifact/success path (if that write fails, don't continue — reconcile). OUR stable correlation/idempotency key (created pre-call, reused for same-Attempt retries) is DISTINCT from the Provider-minted `provider_request_id` (post-call identity).

Job vs Attempt + Artifact key: one Job has many Attempts but one authoritative Attempt at a time via the lease token (a broker duplicate is not a new Attempt). Result Artifact key is deterministic PER-ATTEMPT (`results/{tenant}/{job}/{attempt}/result.json`): same Attempt resumes on the same key; different Attempts never overwrite. Object Storage owns bytes; PostgreSQL owns business truth + Artifact metadata/reference (key/checksum/size/content-type/provenance). Verify by HEAD (metadata-only, unlike GET): existence + checksum + size + content-type. Upload-timeout + matching HEAD -> forward-repair the reference, no overwrite; checksum/metadata mismatch -> CONFLICT (no overwrite/no success, reconcile); DB rollback after upload does NOT undo Object Storage (retain candidate, reconcile/forward-repair or auditable orphan GC).

Guarded completion: final success is ONE PostgreSQL tx under the CURRENT matching `lease_token` — verified Artifact reference + Attempt finished + success Event + Job running->succeeded + lease cleared. Object existence / HTTP 200 / Celery ACK / traces are NOT success; a stale Worker's guarded UPDATE matches 0 rows (keep its object for reconciliation, don't delete).

Outcome classification: timeout + durable dispatch marker -> `pending_reconciliation` (no blind new call); HTTP 200 + invalid body -> Provider CONTRACT FAILURE (durable failed Attempt/Job/Event facts), not success; valid -> Artifact HEAD verify -> guarded completion.

OTel = diagnostic correlation, NOT business truth: propagate/persist trace context HTTP -> Job/Outbox -> Relay -> Worker; reuse the trace association for the same durable Outbox intent on Relay retry, new span id per operation (`trace_id`=trace, `span_id`=one op, Span Link=optional non-parent/child). Logs/traces carry job_id/attempt_id/trace context but NOT a full `provider_request_id` (hash it); metrics use low-cardinality labels (provider, outcome) — never job_id/attempt_id/provider_request_id. Collector/exporter failure must NOT fail a committed Job or trigger a duplicate Provider call; reconstruct evidence from PostgreSQL + Object Storage + Provider ledger.

Authoritative Worker path (`day61_worker_runtime.run_authoritative_attempt`, run by the Celery task): guarded claim (`claim_and_start_attempt`) → tenant + stable correlation key from PostgreSQL durable facts (never the message) → `run_external_operation` under the claim's lease token (Provider HTTP → MinIO PUT/HEAD → guarded completion) → outcome returned VERBATIM. There is NO 'no-Provider, straight-to-succeeded' production path; the Day60 `run_worker_attempt` skeleton is teaching-only. FastAPI acceptance opens a `fastapi.accept_job` ROOT span so the `traceparent` is written into the Outbox payload in the SAME tx; Relay retry reuses the association; a stale Worker returns `lease_lost_no_commit`. Fake Provider is idempotent on the stable `X-Correlation-Key` (one external operation per key; incompatible mode → 409). Fake Provider (separate process, not in-process mock): modes success / timeout (record receipt FIRST, then delay past client timeout) / invalid_response (200, contract-violating body) + an independent request ledger. Proves adapter HTTP integration only — NOT real model cost/rate-limits/production. No new migration (schema already has result_artifacts + provider_request_id + provider_dispatch_started_at); Day60 head stays 0012, lease triple + recovery preserved.

Evidence tiers: 66 Day61 local tests pass. A disposable local INTEGRATION_RUNTIME run verified FastAPI → Outbox Relay → Redis/Celery → fake Provider HTTP → MinIO PUT/HEAD → guarded PostgreSQL completion and Collector trace export. Timeout-after-receipt reached `pending_reconciliation` with no success Artifact and the full lease triple cleared. NOT RUN: real/paid model Provider; production load/security/zero-downtime/multi-replica. No secrets, URLs, keys, tokens, fixture ids committed.

Related: [Day61 lesson](../docs/fastapi/day61-object-storage-provider-adapter-and-opentelemetry-end-to-end-evidence.md) · [Day61 design/runbook](../projects/ai-backend-data-layer/api/day61-object-storage-provider-adapter-and-opentelemetry-end-to-end-evidence-design.md) · [logic](../projects/ai-backend-data-layer/api/day61_provider_artifact_logic.py) · [adapter](../projects/ai-backend-data-layer/api/day61_provider_adapter.py) · [fake provider](../projects/ai-backend-data-layer/api/day61_fake_provider.py) · [tests](../projects/ai-backend-data-layer/api/test_day61_fake_provider_http.py)

## Day62 — Playwright Runtime, Locators and Reliable Async Interaction

Ownership: `Browser` = reusable process runtime; `BrowserContext` = per-task state + fault-isolation boundary (one per task); `Page` = the task's surface. Reuse the Browser, create a NEW Context and Page per task, close the Context in `finally`. A Browser failure invalidates every Context/Page; Task A's failure must NEVER close an independent Context B; a Context-closed `new_page()` is an error.

Locator = a re-resolvable target CONTRACT, not a cached DOM node. Stability comes from a maintained role + accessible name or a stable `data-testid` — NOT dynamic CSS classes or positional `nth()`. Scope within a business region (`form.get_by_role(...)`).

Waiting: `Locator.click()` waits for ACTIONABILITY (visible/enabled/stable/hittable); a business ASSERTION (`expect(results).to_have_text("Results for <q>")`) waits for a business FACT. Actionability ≠ business completion. No fixed `sleep` (guesses time); no `force=True` (hides an actionability failure — wait for overlay hidden / `data-state=ready`; `to_be_hidden()` accepts absent+hidden). `networkidle` is not universal business readiness.

Outcomes: timeout / login redirect / Page crash = UNKNOWN or FAILED precondition — never business `no result`, never blind-retry permission (recovery = Day65). An ASSERTED empty result IS a real business fact (distinct from unknown). Reuse the Day61 rule: timeout ≠ non-execution; observable facts, not impressions, decide claims.

Cleanup honesty: task success = business asserted AND `context.close()` completed. Assertion passed but close failed -> INCOMPLETE (not success). Operation AND cleanup both fail -> preserve the ORIGINAL operation error as primary, record the cleanup failure as diagnostics. Never let a bare `finally: close()` mask the primary error.

Test page discipline: local HTTP (not `file://`) models route/query/request/response and injects a bounded `overlay_delay_ms`; the page's OWN JS clears the overlay, handles the click, and async-renders the result. Playwright NEVER mutates the DOM to fake success. Production drill: a renamed `data-testid` that times out Workers -> pause + correlate + roll back the frontend contract + re-verify; keep timed-out tasks as unknown; never `force=True`/brittle CSS/blind retry.

Artifact `projects/fastapi-playwright/`: `src/day62_interaction_logic.py` (pure outcome/cleanup/locator rules), `src/day62_research_page.py` (controlled HTTP page), `src/day62_browser_task.py` (one Context/task, scoped Locators, no sleep/no force, `finally` cleanup). Evidence tiers: `python3 -m pytest -q tests/` -> 13 passed, 1 skipped (real-Chromium suite gated on `playwright`) — EXECUTED_LOCAL_RUNTIME. NOT RUN by the agent: Python `finally` cleanup + action-timeout against a live browser; Day63 auth/isolation; Day64 artifact flow; Day65 recovery/security; Day66 queue integration; production. No secrets, login state, tenant data, real URLs/tokens, or screenshots committed.

Related: [Day62 lesson](../docs/fastapi/day62-playwright-runtime-locators-and-reliable-async-interaction.md) · [Day62 design/runbook](../projects/fastapi-playwright/docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md) · [interaction logic](../projects/fastapi-playwright/src/day62_interaction_logic.py) · [research page](../projects/fastapi-playwright/src/day62_research_page.py) · [browser task](../projects/fastapi-playwright/src/day62_browser_task.py)

## Day63 — Browser Authentication, Storage State and Tenant Isolation

Two-layer model: Tenant = business authorization/isolation scope; BrowserSession = explicit tenant/owner/origin/identity-bound REVOCABLE authorization capability; storage_state = reusable SENSITIVE auth material (NOT proof of identity); BrowserContext = per-task runtime isolation (never shared live); Lease/Fencing = attempt-owned CONTINUING authority. `tenant_id` alone does not isolate Cookies/Storage/Pages/requests — the fresh Context does; cleanup can't prove isolation.

Safe Task pipeline: validate Job binding (tenant/session/target_origin) → ATOMIC claim (`UPDATE ... RETURNING`: active + not revoked + not expired + lease available) → ONLY the winner reads the protected credential ref → fresh Context from FILTERED storage state → verify POSITIVE identity fact (principal_id/organization_id) at approved Origin → allowed actions + fencing → FINAL fence before publish → publish only if authorized → close Context in `finally`. A non-winning claim reads NO credential and builds NO Context. FINAL fence predicate: session active AND session not expired AND lease_owner==this attempt_id AND lease_token==worker_token AND lease_expires_at>now AND version==claimed — an OLD Attempt with an EXPIRED lease (or a successor-owned lease) is AUTHORIZATION_SESSION_FAILURE and can NEVER publish. Task completion status is distinct from published: SUCCESS = published AND cleanup completed; a published result whose close() FAILED is INCOMPLETE, never SUCCESS; the cleanup error never overwrites the primary business error.

Identity: "no login redirect" is NOT proof; a mutable display name is NOT proof. Verify a stable principal_id/org from an account page or protected `/me` vs expected binding. A tenant's session may NOT be auto-selected; the Job binds an exact server-authorized session_id (client value is only a candidate; Worker re-checks + claims).

Outcomes (each BLOCKS publication; none becomes business `no result`; none permits blind retry): identity mismatch → AUTHORIZATION_SESSION_FAILURE; login redirect / inactive|expired session → AUTHENTICATION_PRECONDITION_FAILED; final lease/fence check timeout → UNKNOWN_AUTHORIZATION_STATE; observed unapproved-Origin navigation/popup → SECURITY_FAILURE (close Context). On identity mismatch write only a SAFE id + close.

Storage state: persist a protected credential REFERENCE + metadata in PostgreSQL; encrypted content in a least-privilege audited secret/object store; NEVER in a Job payload/queue message/log/screenshot even encrypted. Filter exported Origins + Cookie domains to explicit allowlists. The DEFAULT Cookie-domain allowlist is the approved Origin's HOST (parse the hostname, e.g. `https://research.example.test`→`research.example.test`), NEVER the full Origin string; a host-only cookie survives while a `.example.test` / `billing.example.test` cookie is REJECTED by default; Local Storage is kept only for the exact approved Origin. Cross-subdomain SSO is an explicit, audited allowlist exception.

Concurrency/revocation: session metadata = status/expiry/revoked/version + lease_owner=attempt_id/lease_token/lease_expires_at. A 2nd Attempt CANNOT seize an unexpired lease (wait for expiry, then atomic-claim a new token; old token loses authority at the next fence). A new verified login becomes a new active version ONLY after protected-state persistence AND metadata/audit commit both succeed (never overwrite in place; a failed metadata tx leaves a protected INACTIVE orphan). ONLY `state saved + metadata failed` is ORPHAN_INACTIVE; `state NOT saved` is PERSIST_CONSISTENCY_FAILED (no protected material exists — never an orphan, never active). Revocation blocks new claims + fails future fences but does NOT un-send a request already made (Day65 recovery). Rollback drill: roll back code/policy first + pause claims + preserve audit + scope by actual unapproved-Origin evidence + selectively revoke exposed sessions + mark results untrusted + add redirect/popup regression tests; do NOT delete all sessions first and do NOT claim rollback reverses an external request.

Artifact `projects/fastapi-playwright/`: `src/day63_session_gate.py` (pure gate), `src/day63_controlled_login_page.py` (synthetic loopback account/redirect/unapproved-origin page). Evidence: `pytest -q tests/test_day63_session_gate.py tests/test_day63_controlled_login_page_http.py tests/test_day63_playwright_isolation.py` → 36 passed, 1 skipped (real-Chromium isolation gated on `playwright`), EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Chromium isolation/redirect observation; real PostgreSQL atomic claim; credential encryption/KMS/Object Storage; Worker/queue (Day66); production. Day62's 13/1 is NOT reused as Day63 proof. No secrets/credentials/real URLs/tenant data/cookies/tokens/storage-state committed.

Related: [Day63 lesson](../docs/fastapi/day63-browser-authentication-storage-state-and-tenant-isolation.md) · [Day63 design/runbook](../projects/fastapi-playwright/docs/day63-browser-authentication-storage-state-and-tenant-isolation-design.md) · [session gate](../projects/fastapi-playwright/src/day63_session_gate.py) · [controlled account page](../projects/fastapi-playwright/src/day63_controlled_login_page.py) · [tests](../projects/fastapi-playwright/tests/test_day63_session_gate.py)

## Day64 — Dynamic Extraction, Network Events and Artifact Evidence

Core: `page lifecycle signal != extraction readiness != valid Artifact != published business success`. Trusted Artifact publication = authorized Session AND fresh isolated Context AND task-contract business-ready fact AND correctly correlated network/DOM/download evidence AND schema/content validation AND Object Storage HEAD verification AND durable Artifact reference AND final Day63 authorization fence. Only the WHOLE chain publishes.

Readiness: HTTP 200 / page load are observations, not success. READY = expected report_id + terminal business status + required schema. `{status:"generating"}` blocks publication despite 200. DOM vs network: network JSON is PRIMARY structured data (full precision, all rows); DOM corroborates visible/readiness (rounded, virtualized). Never merge sources without a stated role; DOM-primary only when the contract wants visible text.

Observe-before-acting: register the download/response waiter BEFORE the Export click — prevents a MISSED OBSERVATION only; does NOT make a repeated click/re-download/retry idempotent or safe (Day65 recovery). Correlation: a URL substring + 200 is too broad (a background GET poll matches). Use an explicit action identity `POST /api/exports {report_id, client_request_id}` -> `{export_id, status}`. The INITIAL response must STRICTLY match origin+method+endpoint+report_id AND `client_request_id == expected` — a non-empty `export_id` is NEVER a substitute (another action's response is rejected: CLIENT_REQUEST_ID_MISMATCH). The `export_id` from the verified initial response is what a LATER poll/download/status call correlates against (`extract_export_id` + `correlate_followup`). Network metadata is an explicit ALLOW-list of flat fields (action_id/allowed_origin/method/normalized_endpoint/report_id/client_request_id/export_id/response_status/safe_checksum/observed_at); reject unknown keys, nested header/body maps, Cookies, Authorization, tokens, credentials, raw payloads — allow-list, not deny-list.

Download validation: provenance + completed transfer + bounded nonzero size + ACTUAL content type (never the filename extension) + SHA-256 + parse + schema + business constraints. Counts: `artifact_record_count` (validated rows), `source_record_count` (source/API rows), `accepted_count`/`rejected_count` (terminal import). `202 Accepted` / file selection != import success; require a terminal `import_id` + status + counts + rejection summary; `498 accepted, 2 rejected` succeeds ONLY if the contract permits partials. Extraction Contract validates TYPES + VALUES on the ACTUAL records (row_id=integer, score=number, label=non-empty string): FIELD_MISSING / TYPE_MISMATCH (e.g. score is a string) / VALUE_INVALID (empty label) / CONTRACT_MISMATCH (rename/drift without a reviewed rule; a reviewed rename still validates the alias's type). Never silently map; never substitute a hand-written schema_valid=True.

Storage/fence order: object existence != Job success. `HEAD verified -> final FULL fence (active+session-expiry+lease_owner+lease_token+lease_expires_at+version) -> ONE guarded durable txn (Artifact reference + Job publication) committed ONLY if the fence still matches -> commit`. The fence is AT the durable-write boundary, so a fence failure/timeout/revocation commits NOTHING (no "reference committed but publication blocked" state) -> RETAIN_UNPUBLISHED_FENCE. Guarded txn fails -> RETAIN_CANDIDATE_TXN_FAILED; upload timeout + matching HEAD -> FORWARD_REPAIR (reuse verified object, never blind re-upload/overwrite/delete); orphan GC is later, audited, retention-governed. Real PostgreSQL tx NOT RUN (pure model = would-commit/rejected). Rollback (broad-listener release): `Rollback stops future harm. Evidence scopes past harm. Classification decides repair.` -> CONFIRMED_CORRECT / MISATTRIBUTED_UNVERIFIED (untrusted, stop downstream) / UNPUBLISHED_CANDIDATE (retain) / UNKNOWN (reconcile, no blind retry).

Artifact `projects/fastapi-playwright/`: `src/day64_extraction_contract.py` (pure decision core + `assemble_trusted_artifact` orchestrator, reuses `day63_session_gate.final_fence`), `src/day64_controlled_report_page.py` (synthetic SPA + `/api/reports` + `/api/exports`). Evidence: `pytest -q tests/test_day64_extraction_contract.py tests/test_day64_report_page_http.py` -> 25 passed, EXECUTED_LOCAL_RUNTIME (14 pure failure-path + 2 HTTP-loopback). LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Playwright extraction/network/download-upload; real Day61 Object Storage HEAD; real PostgreSQL Artifact-reference tx; Worker/queue (Day66); production. Day63 counts not reused. No secrets/credentials/cookies/storage-state/real URLs/raw payloads/screenshots committed.

Related: [Day64 lesson](../docs/fastapi/day64-dynamic-extraction-network-events-and-artifact-evidence.md) · [Day64 design/runbook](../projects/fastapi-playwright/docs/day64-dynamic-extraction-network-events-and-artifact-evidence-design.md) · [extraction contract](../projects/fastapi-playwright/src/day64_extraction_contract.py) · [report page](../projects/fastapi-playwright/src/day64_controlled_report_page.py) · [tests](../projects/fastapi-playwright/tests/test_day64_extraction_contract.py)

## Day65 — Browser Failure Recovery and Security Boundaries

Core: `no observed completion != proven operation failure`. Browser Task Decision Contract = task/server-side policy is the SOLE authorization source; before-action gate (authorization + Session + lease + website policy + SSRF); after-failure routing (proven retryable -> bounded retry; may-have-happened -> reconcile UNKNOWN_OUTCOME; security boundary -> stop/human review; deadline/budget exhausted -> stop new Attempts); diagnostics private/redacted/audited; incident contain->scope->classify->repair->controlled rollout.

Timeout: a POST-ACTION timeout (request sent, no response) = UNKNOWN_OUTCOME (may have executed) -> reconcile, NOT retry. Only a PROVEN non-start = SAFE_TO_RETRY. Reconcile the ORIGINAL action by strict Day64 identity (client_request_id/report_id/verified export_id) + a server status/audit lookup — NEVER a broad URL+200; a record with a different client_request_id (or origin/method/endpoint/report_id/export_id) is STILL_UNKNOWN. Lifecycle: `202 accepted != completed != published Artifact` — completed/imported -> CONFIRMED_COMPLETED (may publish); accepted/pending/running -> CONFIRMED_ACCEPTED_OR_IN_FLIGHT (received, NOT done: no replay, no publication, keep polling same export_id); authoritative not_found/never_started -> CONFIRMED_NOT_STARTED (may retry). `reconcile_permits_replay`/`reconcile_permits_publication`/`reconcile_next_step`. `classify_timeout`, `reconcile_unknown`.

Diagnostics: screenshots/traces/headers/raw payloads/DOM/Cookies/Authorization/tokens/PII/tenant data are sensitive -> minimal, redacted, private, access-controlled, retention-bounded, audited. NEVER ordinary logs, model context, prompts, or public Artifacts. A screenshot proves page DISPLAY only, not Export/Artifact success. `diagnostics_decision` (DENY_DESTINATION for log/model/prompt/public).

Navigation/SSRF: page content is untrusted input, NOT authorization. Validate scheme + EXACT Origin (host:port) + resolved IP + task scope; block loopback/private/link-local/cloud-metadata (169.254.169.254) by resolved IP; revalidate EVERY redirect + DNS/IP change (DNS rebinding). `navigation_allowed`/`validate_redirect_chain`/`is_prohibited_ip` -> BLOCKED_SCHEME/BLOCKED_ORIGIN/BLOCKED_IP.

Credentials: protected scoped capability, not browser-task data. Release needs current tenant/session/attempt + approved Origin + explicit purpose + valid session + least privilege. Cross-Origin navigation NEVER copies/exports/forwards storage state. `credential_release_allowed` (DENY_ORIGIN_NOT_APPROVED/DENY_TENANT_MISMATCH/...); `cross_origin_forwards_storage_state()`=False.

Instruction authority + CAPTCHA: task contract + server policy are the SOLE authority for target/operation/data/credentials/upload; DOM/page/download/network/model output are untrusted -> overreach = PROMPT_INJECTION_BLOCKED (`instruction_authorized`). CAPTCHA = HUMAN_VERIFICATION_REQUIRED -> human review; never bypass/evade/outsource/disguise as retryable (`classify_captcha`; `is_retryable_business_failure`=False).

Bounded retry: needs explicit retryable class + proven non-start/idempotency + NO UNKNOWN_OUTCOME + NO security stop + valid tenant/session/lease/task authz (revalidate Day63 `final_fence`) + remaining deadline/budget + ONE active owner. Policy: max_attempts, total budget, per-attempt timeout, exp backoff+jitter, retryable-error list, idempotency identity, revalidation, audit. Retry-After > remaining deadline -> RETRY_DEFERRED (no new Attempt); deadline blown -> DEADLINE_EXCEEDED. `retry_eligibility`/`authorization_still_valid`.

Incident (wildcard-origin rollback): contain (roll back policy, pause tasks/new Attempts, block targets, revoke Sessions/rotate creds per evidence) -> scope (version/window, audits, nav decisions, minimized safe evidence) -> classify (BLOCKED_BEFORE_NAVIGATION / UNAPPROVED_NAVIGATION_NO_CREDENTIAL_RELEASE / POSSIBLE_CREDENTIAL_EXPOSURE / PUBLISHED_ARTIFACT_AFFECTED / UNKNOWN) -> repair (restore exact-Origin, regression tests for redirect/DNS-IP/cookie/injection) -> controlled rollout. UNKNOWN is reconciled/investigated, NEVER blindly retried. `incident_phases`/`classify_incident_item`.

Artifact `projects/fastapi-playwright/`: `src/day65_recovery_security_policy.py` (pure decision core). Evidence: `pytest -q tests/test_day65_recovery_security_policy.py` -> 20 passed, EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Playwright timeout/reconciliation, trace/screenshot redaction, redirect/DNS/IP policy, storage-state/Cookie, CAPTCHA, audit lookup, Worker/queue (Day66), integration, production. Day64's 25 passed is NOT reused as Day65 evidence. No secrets/credentials/real URLs/Cookies/tokens/customer data/raw payloads/screenshots/CAPTCHA-bypass committed.

Related: [Day65 lesson](../docs/fastapi/day65-browser-failure-recovery-and-security-boundaries.md) · [Day65 design/runbook](../projects/fastapi-playwright/docs/day65-browser-failure-recovery-and-security-boundaries-design.md) · [recovery/security policy](../projects/fastapi-playwright/src/day65_recovery_security_policy.py) · [tests](../projects/fastapi-playwright/tests/test_day65_recovery_security_policy.py)

## Day66 — Queue-backed Playwright Worker as a Permissioned AI Tool

Core: the LLM PROPOSES a tool call; the backend owns authorization, durable truth, dispatch, execution authority, recovery, audit. `accepted != running != succeeded != published Artifact`. Roles: Provider/LLM = inference + tool-call proposal (no browser, no credentials); AI Backend = authenticate + validate + persist + dispatch + recover + audit; Queue = at-least-once NOTIFICATION (never authority/Secret store); Worker = temporary executor only after a guarded claim + fence.

Proposal validation: an LLM tool call is UNTRUSTED request input. Authorization comes from a SERVER-authorized contract (`ServerAuthorizedContract`: tenant + allowed operation + exact approved Origin + allowed report scope + valid Session binding); the proposal's tenant/Origin/scope must match it EXACTLY and can never widen it (foreign tenant / malicious Origin / out-of-scope report -> reject). `idempotency_key` binds to the request fingerprint; same key + different fingerprint -> reject; same key + same authorized fingerprint -> idempotent replay. Approval is a SERVER fact (`contract.approval_granted`/`approval_id`); the proposal has NO `user_approved` field and can never self-assert approval — necessary but NOT sufficient. `validate_tool_proposal(proposal, contract, existing)` -> ACCEPT_NEW/REPLAY_EXISTING/REJECT_NOT_A_TOOL_CALL/MISSING_IDEMPOTENCY/UNAPPROVED/POLICY_BLOCKED/TENANT_MISMATCH/ORIGIN_NOT_APPROVED/SCOPE_NOT_ALLOWED/SESSION_UNAUTHORIZED/FINGERPRINT_MISMATCH. A tool call becomes a durable Task ONLY at the committed transaction (Provider response = proposal/step 3; then validation; then commit). `becomes_durable_task_at`.

Atomic acceptance: Browser Task + Permissioned Tool Contract + Outbox dispatch intent commit in ONE tx or roll back together; only all-three -> `202 + task_id`. Dispatch via an INDEPENDENT Outbox Relay AFTER commit (a direct in-request publish can be lost after commit before send). `atomic_acceptance`/`dispatch_via_relay_after_commit`.

Envelope: STRICT ALLOWLIST — ONLY `envelope_version`/`event_id`/`task_id`/`trace_id`/`event_type`; ANY extra field (a `session_token`, any credential, an unknown/future field) -> REJECT_UNKNOWN_FIELD (not a denylist), and `event_type` must be an approved browser-task dispatch (else REJECT_EVENT_TYPE). Unsupported version -> dead-letter + ACK, load nothing (no Job/Session/Playwright). Queue fields are never authorization; reload truth from PostgreSQL + protected Session Store. `validate_envelope`.

Ownership + fence: queue delivery = notification; a guarded PostgreSQL `UPDATE ... RETURNING` claim (attempt_id + lease owner/token/expiry) = execution authority, exactly one winner — a claim takes ONLY a no/expired lease, so ANY live lease is rejected (even the SAME attempt_id; no duplicate re-claim/overwrite); an Attempt extends its OWN live lease via `renew_lease` (matching owner+token, pushed-out expiry, NO token rotation, no re-execution). A terminal `succeeded`/publish requires the CURRENT Day63 final fence (owner+token+unexpired lease+version); a stale Worker (superseded token/version, expired lease) can NEVER publish — valid bytes != trusted Artifact. `guarded_claim`/`terminal_publish_allowed` (reuses `day63_session_gate.final_fence`).

Duplicate delivery: commit durable result BEFORE ACK. Redelivery on a terminal task -> read terminal state, do NOT re-run Playwright, ACK the duplicate (do NOT return a result to the Broker). RUNNING + LIVE lease -> owned by another Attempt -> SKIP_ACTIVE_LEASE_ACK (ACK duplicate, never enter Playwright); RUNNING + EXPIRED lease -> Day65 UNKNOWN_OUTCOME reconciliation (lease expiry != no external effect). `on_delivery`/`ack_only_after_durable_commit`.

Recovery/retry: reconcile hand-off -> CONFIRMED_COMPLETED (publish under fence) / ACCEPTED_OR_IN_FLIGHT (keep reconciling, no replay) / CONFIRMED_NOT_STARTED (bounded-retry gate) / STILL_UNKNOWN (retain). A retry is a NEW auditable Attempt (new attempt_id + lease token), never an in-process loop; `worker_retry_decision` reuses the Day65 fenced `authorize_retry`. Cancellation: durable `cancellation_requested` (not immediate `cancelled`) when an external effect may have begun; check before claim + revalidate fence before credential load/critical action/publication. `classify_cancellation`/`cancellation_checkpoints`.

Tool Result + identity: STRICT ALLOWLIST — ONLY `task_id`/`status`/`safe_summary`/`artifact_ref`; ANY other field (a `session_token`, `authorization`, `raw_prompt`, cookies, trace, raw_csv, unknown/future field) -> DENY_UNSAFE_FIELD (not a denylist). The Artifact REFERENCE is access-controlled and never grants object-read. `task_id` stable across attempts; `attempt_id` per attempt; `lease_token` fences one grant; `outbox_event_id` = dispatch intent; `trace_id` links. Audit = STRICT ALLOWLIST: identity + transition + policy/contract version + classification + timestamp + a non-reversible `lease_token_fingerprint`; the raw `lease_token` capability and any unknown/credential field (e.g. `session_token`) are never audit-safe. `shape_tool_result`/`audit_event_is_safe`. Incident (fence-removal regression): contain (roll back the WORKER RELEASE, not just config; pause claims/Attempts; preserve evidence) -> scope -> classify (blocked stale write / stale artifact published / conflicting attempts / unknown) -> repair (restore fence predicate + A/B regression tests) -> controlled rollout; quarantine a stale-published Artifact, never trust/return it to the LLM. `classify_worker_incident`/`incident_phases`.

Artifact `projects/fastapi-playwright/`: `src/day66_queue_backed_permissioned_worker.py` (pure decision/orchestration core reusing Day63 fence + Day65 recovery). Evidence: `pytest -q tests/test_day66_queue_backed_permissioned_worker.py` -> 14 passed, EXECUTED_LOCAL_RUNTIME. LIVE classroom artifact was CONCEPTUAL_STATIC. NOT RUN: real Provider/LLM tool loop, guarded PostgreSQL concurrent claim, Outbox Relay/Broker duplicate delivery, Celery ACK/redelivery, lease expiry/recovery, Playwright execution, Session revocation/cancellation, Object Storage publication, integration, production. Day65's 20 passed and earlier evidence are NOT reused as Day66 evidence. No secrets/credentials/real URLs/Cookies/storage state/Authorization/Provider keys/customer data/raw traces/screenshots/DOM/network committed.

Related: [Day66 lesson](../docs/fastapi/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool.md) · [Day66 design/runbook](../projects/fastapi-playwright/docs/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool-design.md) · [permissioned worker core](../projects/fastapi-playwright/src/day66_queue_backed_permissioned_worker.py) · [tests](../projects/fastapi-playwright/tests/test_day66_queue_backed_permissioned_worker.py)

## Day67 — n8n Workflow Model, Triggers, FastAPI Integration and Responsibility Boundaries

Core: n8n is permissioned ORCHESTRATION only; FastAPI stays the trusted business + security boundary (Day66 ownership UNCHANGED). n8n model = `trigger -> execution -> nodes -> result`. A workflow node is one more untrusted caller in front of FastAPI — it may ASK, it never creates/mutates a durable Task and never gets direct DB/queue/worker access.

Boundary: n8n -> authenticated FastAPI (HTTP Request node ASKS; FastAPI transaction creates Task + contract + outbox). Never let n8n touch PostgreSQL/queue/worker directly, not even read-only (schema coupling, bypasses policy/audit, misreads transient lease/state). Student: “因为FastAPI是受信任的业务与安全边界”; “没有node有权创建”.

Acceptance: a Webhook receipt != FastAPI durable acceptance. `202 + task_id` is honest ONLY after FastAPI commits. n8n crash before acceptance -> return 502/503 or allow upstream retry; never invent a task_id.

Triggers: Test URL = temporary manual-listening/debug lifecycle (exists only while listening; NOT a registered production endpoint — the real problem behind flakiness is lifecycle, not concurrency). Production URL needs a published/activated workflow, but production availability still != durable backend acceptance. Webhook Trigger = external request; Schedule Trigger = internal periodic work (reconciliation) that calls an authenticated FastAPI reconciliation API, never scans `browser_tasks`.

Identity: a shared n8n service credential proves the calling service, NOT the tenant/user/action. Don't trust body `tenant_id`/`user_id`; don't store/forward a long-lived user login token in n8n execution data. Safer: FastAPI resolves trusted context by `request_id`, or a short-lived signed delegation token (tenant + user + allowed action + request_id + expiry).

Retry (3 layers): n8n owns whether to RE-SEND an uncertain transport call; FastAPI owns BUSINESS IDEMPOTENCY (persist/enforce reused request_id/idempotency key -> redelivery returns existing task_id, no duplicate); worker owns EXECUTION retry. Model = “n8n can resend; FastAPI collapses the same intent.” Reconciliation idempotency basis = `task_id + recovery_action + recovery_generation` (Task identity alone is insufficient).

Rollback: stop the blast radius FIRST (deactivate the bad workflow / publish a prior version) -> scope affected requests from n8n execution history + authoritative FastAPI records -> compensate via FastAPI controlled cancellation/compensation/reconciliation. NEVER delete durable Task records as a rollback mechanism.

Runtime honesty: a configured-looking node is NOT runtime proof — first run misrouted a malformed request into the HTTP branch and returned an empty 200 (an `$json...` expression didn't evaluate); fixed with explicit `{{ $json... }}`. Reproduce locally (Execute workflow / listen on Test URL, then `curl -i -X POST http://localhost:5678/webhook-test/day67/research-report -H 'Content-Type: application/json' -d '{"report_scope":""}'`) -> HTTP 400 `{ "error": "invalid_request", "message": "report_scope and request_id are required" }`; the IF false branch + Respond ran, HTTP Request did NOT run (EXECUTED_LOCAL_RUNTIME; this covers the false branch only — a local Test URL, not CI/production). Audit boundary: n8n execution history is real ORCHESTRATION evidence but is NOT the authoritative business audit and cannot atomically commit business state with an external side effect — FastAPI/DB own business facts, authz, idempotency, audit. NOT RUN/NOT CONFIGURED: valid FastAPI path, service auth, durable Task, PostgreSQL, queue/outbox, worker execution, published Production URL, production. HTTP endpoint was an unverified placeholder `http://host.docker.internal:8000/api/v1/browser-tasks`, auth `None`; no exported workflow JSON captured. No secrets committed.

Related: [Day67 lesson](../docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md) · [n8n-workflows project](../projects/n8n-workflows/README.md) · Previous: [Day66 lesson](../docs/fastapi/day66-queue-backed-playwright-worker-as-a-permissioned-ai-tool.md)

## Day68 — Long-running AI Jobs: Polling, Callback, Correlation and Idempotency

Core: after `202 + task_id`, observation != durable truth. An n8n execution timeout, Poll timeout, HTTP 503, missing/duplicate/out-of-order Callback does NOT by itself change the Task's business state (Day67 boundary unchanged: n8n orchestrates/observes; FastAPI/PostgreSQL owns truth/authz/idempotency/recovery/audit). Do NOT mark failed or recreate a still-running paid Task.

Lifecycle: `n8n execution timeout != durable Task failure`. Recreating risks duplicate Provider cost + duplicate side effects + conflicting Artifacts. Observe or reconcile the EXISTING task_id.

Polling (observation of an existing Task; retrying a poll != retrying the job): `Wait(bounded interval/backoff) -> GET /api/v1/browser-tasks/{task_id} -> Switch(Day66 TaskState)`: ACCEPTED/RUNNING -> backoff -> poll same task_id; CANCELLATION_REQUESTED -> keep observing until terminal (or reconcile); SUCCEEDED -> consume verified artifact_ref; FAILED/CANCELLED -> terminal; timeout/429/503/invalid -> retain task_id, retry or reconcile. (CONCEPTUAL CONTRACT: route + TaskState switch are design only — ROUTE NOT IMPLEMENTED, RUNTIME NOT RUN; use the Day66 Browser Task states only, not a generic queued/expired vocabulary.) Bounds: interval/backoff + observation deadline + max attempts + terminal stops. 503 = observation channel down, NOT task failure; 404 != auto business failure (identity/tenant/retention/integration — investigate). Audit logs = investigation evidence, NOT authoritative state/recovery.

Acceptance idempotency (lost POST response): resend the SAME business `request_id`/idempotency key; FastAPI atomically collapses same intent -> existing task_id. New request_id = new command (may duplicate). Fingerprint bind: same key + same meaning -> existing task_id; same key + different meaning -> 409.

Identities: `request_id` (one logical acceptance command, stable across lost-response retries) · `task_id` (durable backend Task) · `correlation_id` (stable business-chain association, NOT auth/authz) · `event_id` (stable callback identity; deduped AND fingerprint-bound) · `task_version` (monotonic ordering/conflict — MODELED / NOT IMPLEMENTED: not in the Day66 Task model or any published schema; a real run needs an API/callback contract field + durable monotonic version/authoritative event sequence + Day48-style forward-safe additive migration + atomic increment/read + legal-transition enforcement) · `trace_id`/poll-attempt (one concrete attempt, may change).

Callback = AT-LEAST-ONCE (NO exactly-once delivery or exactly-once cross-system effect claim): authenticate -> validate schema -> match task_id+correlation_id -> compute/validate event fingerprint -> ATOMICALLY enforce event_id+fingerprint (same event_id+same meaning=idempotent no-op; same event_id+different meaning=integration/security CONFLICT, do not act) -> task_version ordering (reject stale/conflicting) -> verify legal transition -> authoritative FastAPI confirm when required -> ONE idempotent downstream action at a boundary that durably enforces the idempotency key (e.g. `event_id:publish-report`; duplicate-safe idempotent logical outcome; external targets enforce their own key or are reconciled). Event fingerprint = event_type + task_id + correlation_id + task_version + artifact_ref/result identity (NO Secrets/raw payloads). n8n history is NOT the idempotency store. Correlation mismatch (right task_id, wrong correlation_id) -> do NOT publish, preserve safe metadata, query FastAPI, reconcile; correlation matching != authentication. Ordering: incoming version < processed -> stale no-op/ack; == -> identical=idempotent no-op, conflicting=integration error; > -> verify legal transition. `arrival order != business-state order`.

Incident (release creates replacement Tasks after failed polls): contain (deactivate/rollback workflow, stop new Tasks) -> scope (workflow version/window, original+replacement request_ids/task_ids/correlation_ids, Attempts, Provider-dispatch + Artifact evidence) -> classify (queued+no evidence -> FastAPI durable cancellation; running+proven no Provider call -> cooperative cancel; running+external possible/unknown -> PENDING_RECONCILIATION no blind retry; succeeded+verified Artifact -> preserve, compensate duplicate downstream; terminal -> preserve + inspect external effect) -> cancel/reconcile/compensate via FastAPI -> verify -> controlled rollout. Never bulk-delete/bulk-cancel; deletion cannot undo an external side effect.

Evidence: Day68 CONCEPTUAL_STATIC (state-machine/contract design). NOT RUN: n8n workflow runtime, valid FastAPI acceptance/status integration, real Polling loop (Wait/Switch/503/backoff/deadline), real Callback reachability/auth/duplicate/ack-loss/replay/mismatch/out-of-order, real PostgreSQL idempotency/version/terminal, real Worker/Provider duplicate-call prevention + cancel/reconcile, production. No exported n8n JSON. Day67's 400 is NOT Day68 evidence. No secrets/tokens/real callback URLs/tenant data/Provider payloads committed.

Related: [Day68 lesson](../docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md) · [n8n-workflows project](../projects/n8n-workflows/README.md) · Previous: [Day67 lesson](../docs/fastapi/day67-n8n-workflow-model-triggers-fastapi-integration-and-responsibility-boundaries.md)

## Day69 — Human Approval, Retry, Secrets, Audit and Error Workflows

Core: harden the Day68 long-running contract with risk-based human approval + classified recovery + Secret boundaries + authoritative audit + incident hardening. Boundary UNCHANGED: n8n orchestrates; FastAPI/PostgreSQL owns durable truth/authz/idempotency/recovery/audit. Human decides risk; backend verifies authority + persists truth; n8n never owns approval/recovery truth.

Approval is RISK-BASED (NOT every AI output): low-risk reversible -> auto-authorize under a durable tenant pre-authorization policy; high-risk irreversible (external publish/payment/delete/prod change) -> explicit human approval by an authorized TENANT role (Report Owner/Manager/Tenant Admin/Compliance), not platform staff. Validation (schema/security/artifact/grounding) = evidence, NOT permission. Four questions: Validation=evidence · Authorization=who may decide · Approval=whether to act · Audit=who decided what/when/policy/exact object+version.

Exact binding (v7 approval can NEVER authorize v8): Approval binds approval_id+tenant_id+task_id+artifact_id/version+action+status+requested_by+role/policy version+decided_by+decided_at+expires_at. Stable chain IDs: task_id/correlation_id/tenant_id. NEW for changed content/action: approval_id, event_id, publication operation_id, publication idempotency key.

Lifecycle (independent of n8n execution): PENDING -> APPROVED|REJECTED|EXPIRED|CANCELLED. `n8n execution timeout != durable Approval state`; PENDING holds until backend-owned expires_at; a new n8n execution observes the SAME approval_id; late approve on EXPIRED -> rejected + audited. n8n must NOT query the DB directly — it calls authenticated FastAPI; FastAPI enforces tenant/authz and reads PostgreSQL.

Retry = classified recovery, not replay. `HTTP timeout -> OUTCOME_UNKNOWN`. Keep operation_id + idempotency key (`approval-301:publish-report:artifact-v7`), query authenticated FastAPI status/reconciliation: SUCCEEDED->no republish; PROCESSING->observe; FAILED_TERMINAL->no blind retry; PENDING_RECONCILIATION->reconcile; NOT_FOUND->reissue SAME logical command + SAME key. Errors: 429/transient503->backoff+jitter+Retry-After; write timeout->query/reconcile first; 400/422->fix no auto-retry; 401->stop+credential rotation; 403->stop+investigate; 409 idempotency-meaning conflict->stop+investigate; rejected/expired approval->business terminal; unknown external->PENDING_RECONCILIATION.

Secrets: workflow=credential REFERENCE; Credential Store/Secret Manager=real secret; runtime=controlled injection; logs/audit/export/evidence-pack = NEVER Token/Authorization header/API key/cookie/private key/raw payload/tenant content. 401 -> stop, preserve safe evidence, rotate, revalidate approval/version, resume same operation_id (never blind retry / never log the header).

Audit: approvals (current state) + append-only approval_events (transition history) committed ATOMICALLY; corrections/revocation/compensation APPEND, never rewrite. Append-only is NOT automatically tamper-proof (needs perms/retention/monitoring/backup). Delivery is AT-LEAST-ONCE (no exactly-once claim): same event_id+same fingerprint = duplicate-safe no-op (one business `approval.approved`, many receipts/traces); same event_id+DIFFERENT fingerprint = integration/security CONFLICT, no action (query FastAPI, never authorize the changed artifact). current state != transition history; operational log != business audit; n8n history != authoritative audit.

Error Workflow: resume the SMALLEST safe operation boundary — `workflow retry != business operation retry`. A post-publication notification 503 retries ONLY the notification (status lookup if available; same-key idempotent retry if available; else reconcile/escalate by duplicate risk); completed Task/Approval/Publication are facts, not steps to redo.

Incident: contain -> revoke/rotate -> preserve evidence -> scope -> classify -> cancel/reconcile/compensate -> verify -> regression checks -> controlled rollout. Rollback stops FUTURE harm only (does not undo committed Tasks/Provider cost/external publications). Classify: published-without-approval -> preserve SUCCEEDED + policy-violation record + compensate (never retro-approve/delete); provably-unstarted duplicate Task (ACCEPTED, no Attempt, provider_dispatch_started_at=null) -> FastAPI durable guarded cancellation (late queue delivery observes cancelled + no-op); RUNNING + provider_dispatch_started_at!=null + no stored response -> PENDING_RECONCILIATION. Credential exposure window runs until revocation (may exceed the failure window); missing logs != no operation. `publication succeeded` and `publication complied with policy` are SEPARATE dimensions.

Evidence: Day69 CONCEPTUAL_STATIC (design review only). NOT RUN: n8n runtime, FastAPI approval/publication integration, real Approval callback/approver auth, PostgreSQL Approval schema/migration/audit-events/Outbox, retry/backoff/error workflow, callback duplicate/fingerprint-conflict, credential-store/rotate/redaction, publication/notification target/reconciliation, Worker/Provider/Browser-Tool, rollback/kill-switch/canary, production. No exported n8n JSON; Day67's 400 / Day68's contract NOT reused. No secrets/tokens/real callback URLs/tenant data/Provider payloads committed.

Related: [Day69 lesson](../docs/fastapi/day69-human-approval-retry-secrets-audit-and-error-workflows.md) · [n8n-workflows project](../projects/n8n-workflows/README.md) · Previous: [Day68 lesson](../docs/fastapi/day68-long-running-ai-jobs-polling-callback-correlation-and-idempotency.md)
