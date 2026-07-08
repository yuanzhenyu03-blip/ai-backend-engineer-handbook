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
