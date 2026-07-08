# Lesson 14 — Mini Project & Backend Architecture

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Integration / Capstone

Estimated Time: 6-7 hours

Prerequisite: Day13 — Async Programming

Next Lesson: Phase 2 — Engineering Foundations (Git, Linux, Docker)

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Design a layered AI backend: API, Service, Browser, LLM, Repository, Database.
* Explain the single responsibility of each layer and what it must NOT do.
* Keep FastAPI routers thin and push logic into the Service layer.
* Use dependency injection to build stateless, testable services.
* Treat the Browser and LLM as infrastructure behind interfaces.
* Apply the Repository pattern to hide the database.
* Reason about worker architecture, throughput, and bottlenecks.
* Apply Semaphore, retry, and exponential backoff for downstream limits.
* Answer backend architecture interview questions like a real engineer.

---

# Why This Matters

Day14 is not a syntax lesson.

Today you integrate Day01–Day13 into one production-shaped AI backend.

Tech Lead Question:

A junior engineer says "it works on my machine, the endpoint returns the summary." Is the
system done?

Think first.

Student Answer:

"Not necessarily. Working once is not the same as an architecture that scales, is testable,
and survives failure."

Tech Lead Correction:

Exactly.

The interview and the job are not about making one request work.

They are about **how the system is structured**.

```text
Works once      -> a script
Well structured -> a system
```

An AI backend that scrapes a page, summarizes it with an LLM, and stores the result touches
every hard problem at once:

```text
HTTP handling      (FastAPI)
Business workflow  (Service)
Infrastructure     (Browser, LLM)
Persistence        (Repository, Database)
Concurrency        (async, workers, semaphores)
Failure handling   (retry, backoff, cancellation)
```

The motivation before the code:

```text
Architecture decides whether a system can grow, be tested, and be maintained
by a team you have not met yet.
```

That is what a Tech Lead reviews, and what an overseas interview probes.

---

# Roadmap Position

Day01–Day13 built the parts.

Day14 assembles them into a system.

```text
Day01-Day11: Python engineering thinking
        |
        v
Day12: Context Managers (resource cleanup)
        |
        v
Day13: Async Programming (throughput)
        |
        v
Day14: Mini Project & Backend Architecture
        |
        v
Phase 2: Git, Linux, Docker
        |
        v
Phase 3+: Backend, FastAPI, databases, AI systems
```

Every earlier lesson reappears as a layer or a decision:

```text
OOP + composition   -> layer boundaries and dependency injection
Type hints          -> interface contracts between layers
Exceptions          -> failure handling across layers
Context managers    -> resource cleanup in Browser and DB
Async + semaphore   -> worker throughput and rate limits
```

This is why Day14 closes Phase 1.

---

# Lesson Map

```text
Today's Lesson

1. Why Architecture Matters
2. Layered Architecture Overview
3. API / Router Layer
4. Service Layer
5. Browser Layer
6. LLM Layer
7. Repository Layer
8. Engineering Thinking (SoC, SRP, DI, Stateless)
9. Production Topics (Workers, Throughput, Retry)
10. FastAPI Connections
11. Playwright Connections
12. AI Backend Connections
13. Mock Interview
14. Exercises and Review
```

---

# Estimated Study Time

```text
Reading: 120-150 minutes
Architecture design: 60-90 minutes
Coding: 90-120 minutes
Mock interview: 45-60 minutes

Total: 6-7 hours
```

---

# Main Concepts

## Concept 1: Layered Architecture

The system is a stack of layers, each with one responsibility.

```text
        API / Router      -> HTTP in, HTTP out
             |
             v
        Service           -> orchestration, business workflow
             |
             v
        Browser           -> infrastructure: page extraction
             |
             v
        LLM               -> infrastructure: summarization
             |
             v
        Repository        -> persistence abstraction
             |
             v
        Database          -> storage
```

Tech Lead Question:

Why not put everything in the route function? It is fewer files.

Think first.

Student Answer:

"Because one giant function mixes HTTP, business logic, scraping, LLM calls, and SQL. It is
impossible to test or reuse, and every change risks breaking something unrelated."

Tech Lead Correction:

Exactly.

Each layer has a job and, just as important, things it must NOT do.

```text
Layer      SHOULD                         SHOULD NOT
-------    ----------------------------   -----------------------------
API        validate + delegate            contain business logic
Service    orchestrate workflow           know about HTTP or SQL
Browser    extract page data              return FastAPI models or JSON
LLM        summarize / generate           know about HTTP requests
Repository read/write via abstraction     leak SQL details upward
Database   store data                     contain business rules
```

The mental model:

```text
Data flows down. Dependencies point inward. Each layer trusts an interface, not a detail.
```

## Concept 2: API / Router Layer

The router is thin.

Its only job is to validate input and delegate.

```python
from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/summarize", response_model=SummaryResponse)
async def summarize(
    request: SummarizeRequest,
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    result = await service.summarize(request.url)
    return SummaryResponse(summary=result.summary, task_id=result.task_id)
```

Responsibilities:

```text
Parameter validation   -> via the Request Model (Pydantic)
Response shaping        -> via the Response Model
Route registration      -> APIRouter, included in main.py
Delegation              -> call the Service, return its result
```

Tech Lead Question:

Should the router call OpenAI directly?

Think first.

Student Answer:

"No. That is business/infrastructure work. The router should only translate HTTP to a service
call."

Tech Lead Correction:

Correct.

`main.py` only wires things together: it creates the app, includes routers, and configures
dependencies. It is not where logic lives.

Production Risk:

```text
Fat routers become untestable and duplicate logic across endpoints.
```

## Concept 3: Service Layer

The Service orchestrates the workflow.

```python
class SummaryService:
    def __init__(self, browser: BrowserClient, llm: LLMClient, repo: TaskRepository) -> None:
        self.browser = browser
        self.llm = llm
        self.repo = repo

    async def summarize(self, url: str) -> SummaryResult:
        text = await self.browser.extract_text(url)
        summary = await self.llm.summarize(text)
        task = await self.repo.save_task(url=url, summary=summary)
        return SummaryResult(summary=summary, task_id=task.id)
```

Responsibilities:

```text
Workflow orchestration   -> extract -> summarize -> save
Business logic           -> what the feature means
Dependency injection     -> receives browser, llm, repo
Stateless                -> no per-request mutable state on the instance
```

Tech Lead Question:

Why should the Service not contain HTTP logic like status codes?

Think first.

Student Answer:

"Because HTTP is a delivery detail. If the Service knew about HTTP, I could not reuse it in a
worker, a CLI, or a test without a web request."

Tech Lead Correction:

Exactly.

Engineering Thinking:

The Service depends on **interfaces** (`BrowserClient`, `LLMClient`, `TaskRepository`), not
concrete implementations.

```text
Service -> depends on abstractions -> swap real/fake without changing the workflow
```

Production Risk — Shared Mutable State:

```python
class SummaryService:
    cache = {}   # BAD: shared across all requests, data leaks between users
```

A stateless service keeps request data in parameters and return values, not on the instance.

## Concept 4: Browser Layer

The Browser is infrastructure, wrapped as a tool.

```python
class BrowserClient:
    def __init__(self, browser: Browser) -> None:
        self.browser = browser

    async def extract_text(self, url: str) -> str:
        context = await self.browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(url)
            return await page.inner_text("body")
        finally:
            await context.close()
```

Responsibilities:

```text
Wrap Playwright behind a clean method
Return DATA (plain text), not JSON or FastAPI models
Own its own resource cleanup (Day12: close context in finally)
```

Tech Lead Question:

Should `BrowserClient` import and return a `SummaryResponse` model?

Think first.

Student Answer:

"No. The browser layer should not depend on FastAPI models. It returns plain data; the Service
decides what to do with it."

Tech Lead Correction:

Correct.

```text
Browser depends on FastAPI  -> wrong direction, tight coupling
Browser returns data        -> reusable by any caller
```

Production Risk:

Each `BrowserContext` costs memory. Concurrent scraping must be bounded with a Semaphore
(Day13).

## Concept 5: LLM Layer

The LLM layer hides the provider behind an interface.

```python
from typing import Protocol


class LLMClient(Protocol):
    async def summarize(self, text: str) -> str: ...


class OpenAIClient:
    async def summarize(self, text: str) -> str:
        ...


class AnthropicClient:
    async def summarize(self, text: str) -> str:
        ...
```

Responsibilities:

```text
Abstract the provider (OpenAI, Anthropic, Gemini) behind one interface
Multi-provider architecture: swap providers without touching the Service
Own retries and rate-limit handling for its calls
```

Tech Lead Question:

Why define an `LLMClient` interface instead of calling `openai.ChatCompletion` in the Service?

Think first.

Student Answer:

"So I can switch providers, add fallbacks, or mock the LLM in tests without rewriting the
business workflow."

Tech Lead Correction:

Exactly.

```text
Interface First Development:
Design the contract, then implement providers behind it.
```

Multi-provider value:

```text
Provider outage     -> fail over to a second provider
Cost / quality      -> route different tasks to different models
Testing             -> inject a fake LLM
```

## Concept 6: Repository Layer

The Repository hides the database behind methods.

```python
class TaskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def save_task(self, url: str, summary: str) -> Task:
        ...

    async def get_task(self, task_id: int) -> Task | None:
        ...
```

Responsibilities:

```text
Repository pattern: save_task, get_task, list_tasks
Database abstraction: the Service never writes SQL
Return domain objects (Task), not raw rows
```

Tech Lead Question:

Why not run SQL directly inside the Service?

Think first.

Student Answer:

"Because then the Service is coupled to the database. Switching Postgres for something else, or
testing without a real DB, becomes painful."

Tech Lead Correction:

Correct.

```text
Service -> Repository interface -> Database
```

The Repository is where persistence details live and stop.

---

# Engineering Thinking

## Separation of Concerns

Each layer owns one concern.

```text
API        -> transport
Service    -> workflow
Browser    -> extraction
LLM        -> generation
Repository -> persistence
```

A change in one concern should not ripple through the others.

## Single Responsibility Principle

A class should have one reason to change.

```text
SummaryService changes when the workflow changes.
BrowserClient changes when scraping changes.
TaskRepository changes when persistence changes.
```

If a class changes for many unrelated reasons, it is doing too much.

## Low Coupling, High Cohesion

```text
Low coupling  -> layers depend on interfaces, not internals
High cohesion -> everything in a layer serves one purpose
```

Tech Lead Question:

Which is healthier: one 800-line "service" or five focused classes?

Think first.

Student Answer:

"Five focused classes. Each is small, testable, and has a single reason to change."

Tech Lead Correction:

Exactly. Cohesion up, coupling down.

## Dependency Injection

Dependencies are passed in, not created inside.

```python
service = SummaryService(browser=browser, llm=llm, repo=repo)
```

Benefits:

```text
Testable   -> inject fakes
Swappable  -> change providers
Explicit   -> ownership is visible
```

## Stateless Service and Shared Mutable State

```text
Stateless service    -> safe under concurrency, horizontally scalable
Shared mutable state -> data leaks, race conditions, hard-to-debug bugs
```

Keep request state in parameters and return values, not on long-lived instances.

## Interface First Development and Architecture Before Coding

```text
1. Design the layers and their interfaces.
2. Agree on the contracts (types).
3. Then implement behind those contracts.
```

Tech Lead Question:

Why design interfaces before writing implementations?

Think first.

Student Answer:

"Because the interface is the agreement. If I code first, the structure is accidental and hard
to change."

Tech Lead Correction:

Exactly. Architecture before coding turns a script into a system.

---

# Production Topics

## Worker Architecture: Async vs Worker

```text
Async        -> one process overlaps I/O waiting (high throughput per worker)
Worker Pool  -> many processes/replicas handle CPU and isolation
```

Tech Lead Question:

Summarizing 10,000 URLs: do you scale with more `await`, or more workers?

Think first.

Student Answer:

"Both, at different levels. Async raises per-worker throughput for I/O; workers and horizontal
scaling add capacity and isolation."

Tech Lead Correction:

Correct.

```text
Async     -> concurrency inside one worker
Workers   -> parallelism across workers
Scaling   -> add replicas behind a queue
```

## Throughput and Bottleneck Analysis

```text
Find the slowest downstream dependency:
OpenAI rate limit? DB pool? Browser memory?
Optimize the bottleneck, not random code.
```

Adding concurrency past the bottleneck only creates errors.

## Semaphore, Retry, Exponential Backoff, HTTP 429

```python
sem = asyncio.Semaphore(10)

async def summarize_one(url: str) -> str:
    async with sem:
        for attempt in range(5):
            try:
                return await service.summarize(url)
            except RateLimitError:
                await asyncio.sleep(2 ** attempt)   # exponential backoff
        raise
```

```text
Semaphore    -> bound concurrency to downstream capacity
Retry        -> recover from transient failures
Backoff      -> exponential wait to respect HTTP 429
```

## Browser and LLM Resource Management

```text
Browser: bound concurrent contexts, close each in finally (Day12 + Day13)
LLM: respect rate limits, retry with backoff, fail over across providers
```

---

# Classroom Exercises

## Level 1: API Layer

Question:

The route function scrapes, calls OpenAI, and writes SQL. What is wrong?

Think First:

What is the router's single responsibility?

Starter Code:

```python
@router.post("/summarize")
async def summarize(url: str):
    text = await scrape(url)
    summary = await openai_call(text)
    await db.execute("INSERT ...")
    return {"summary": summary}
```

Expected Output:

Move scraping, LLM, and persistence into a service; keep the router thin.

Explanation:

The router should validate and delegate only.

Follow-up Question:

What belongs in `main.py` versus the router?

## Level 2: Service Layer

Question:

Design `SummaryService.summarize(url)`.

Think First:

What does the service orchestrate?

Starter Code:

```python
class SummaryService:
    ...
```

Expected Output:

Extract text, summarize, save, return a result — using injected dependencies.

Explanation:

The service owns the workflow, not HTTP or SQL.

Follow-up Question:

Why should the service not know HTTP status codes?

## Level 3: Browser Layer

Question:

Why should `BrowserClient` return text instead of a `SummaryResponse`?

Think First:

Which direction should dependencies point?

Starter Code:

```python
async def extract_text(self, url: str) -> str:
    ...
```

Expected Output:

Return plain text; the browser layer must not depend on FastAPI models.

Explanation:

Returning data keeps the layer reusable and decoupled.

Follow-up Question:

Where is the browser context closed?

## Level 4: Dependency Injection

Question:

Wire `SummaryService` with `Depends()`.

Think First:

Who creates the service's dependencies?

Starter Code:

```python
def get_summary_service(...):
    ...
```

Expected Output:

Inject browser, llm, and repo, and return a `SummaryService`.

Explanation:

Dependencies are injected, not constructed in the route.

Follow-up Question:

How does this help testing?

## Level 5: Repository Pattern

Question:

Add `save_task` and `get_task` to a repository.

Think First:

Should the service see SQL?

Starter Code:

```python
class TaskRepository:
    ...
```

Expected Output:

Methods that hide the database and return domain objects.

Explanation:

Persistence details stop at the repository.

Follow-up Question:

Why return a `Task` object instead of a raw row?

## Level 6: Task Status Design

Question:

The summary takes 30 seconds. Design the API so it stays responsive.

Think First:

Should the client hold the connection for 30 seconds?

Starter Code:

```text
POST /summarize -> ???
GET /tasks/{id} -> ???
```

Expected Output:

Return a `task_id` immediately; process in a worker; expose task status.

Explanation:

Long work moves to a queue and worker; the API returns fast.

Follow-up Question:

What states does a task go through?

## Level 7: Retry Strategy

Question:

Handle OpenAI HTTP 429.

Think First:

Retry immediately or wait longer each time?

Starter Code:

```python
for attempt in range(5):
    try:
        return await llm.summarize(text)
    except RateLimitError:
        ...
```

Expected Output:

Exponential backoff: `await asyncio.sleep(2 ** attempt)`.

Explanation:

Backoff respects rate limits and reduces overload.

Follow-up Question:

Why not retry forever with no delay?

## Level 8: Worker Architecture

Question:

Scale summarization to 10,000 URLs.

Think First:

Where is the bottleneck?

Starter Code:

```text
Queue -> Workers -> Service -> downstream
```

Expected Output:

Bounded workers pulling from a queue, semaphores per downstream dependency.

Explanation:

Async raises per-worker throughput; workers and replicas add capacity.

Follow-up Question:

How do you find the real bottleneck?

## Level 9: System Design

Question:

Draw the full AI Summary Service architecture.

Think First:

What are the layers and infrastructure pieces?

Expected Output:

```text
API -> Service -> (Browser, LLM) -> Repository -> Database
Queue + Workers + Redis + PostgreSQL + OpenAI + multi-provider
```

Explanation:

Layers for structure, infrastructure for scale.

Follow-up Question:

Which parts are stateless, and which hold state?

## Level 10: Mock Interview

Question:

Explain a trade-off you made in this architecture.

Think First:

What did you give up for what benefit?

Expected Output:

A clear trade-off, e.g. bounded concurrency (lower peak speed) for stable throughput
(reliability and fewer 429s).

Explanation:

Senior answers name trade-offs, not just correct designs.

Follow-up Question:

When would you choose the other side of the trade-off?

---

# FastAPI Connections

The full request path through the layers:

```text
Request
   |
   v
Router            -> validate request model
   |
   v
Depends()         -> inject the Service and its dependencies
   |
   v
Service           -> orchestrate the workflow
   |
   v
Browser           -> extract page text
   |
   v
LLM               -> summarize
   |
   v
Repository        -> save the task
   |
   v
Database          -> persist
   |
   v
Response          -> shaped by the response model
```

## Dependency Wiring

```python
def get_summary_service(
    browser: BrowserClient = Depends(get_browser_client),
    llm: LLMClient = Depends(get_llm_client),
    repo: TaskRepository = Depends(get_task_repository),
) -> SummaryService:
    return SummaryService(browser=browser, llm=llm, repo=repo)
```

FastAPI's `Depends()` is dependency injection at the framework level: each request gets a
service wired from its dependencies.

What to watch for:

```text
Keep routers thin.
Inject services; do not construct them inside routes.
Let the request Task be cancellable on client disconnect (Day13).
```

---

# Playwright Connections

The Browser layer is the concrete Playwright integration.

```python
class BrowserClient:
    async def extract_text(self, url: str) -> str:
        async with self.sem:                     # bound concurrency
            context = await self.browser.new_context()
            try:
                page = await context.new_page()
                await page.goto(url)
                await page.locator("body").wait_for()
                return await page.inner_text("body")
            finally:
                await context.close()             # always clean up
```

Rules carried from earlier lessons:

```text
Share the Browser, isolate a BrowserContext per job (Day11 ownership).
Close the context in finally, even on cancellation (Day12).
Bound concurrent contexts with a Semaphore (Day13).
Return plain data, never FastAPI models.
```

---

# AI Backend Connections

A concrete AI Summary Service ties it together.

```text
POST /summarize
   |
   v
SummaryService
   |
   +--> BrowserClient.extract_text(url)     (Playwright)
   |
   +--> LLMClient.summarize(text)           (OpenAI / Anthropic / Gemini)
   |
   +--> TaskRepository.save_task(...)        (PostgreSQL)
```

Scaling it for volume:

```text
Task Queue    -> accept jobs, return a task_id immediately
Worker Pool   -> workers pull jobs and run the Service
Redis         -> queue + cache + rate-limit coordination
PostgreSQL    -> durable task storage
OpenAI        -> summarization under a semaphore with backoff
Multi-provider-> fail over when a provider is down or rate-limited
```

Tech Lead Question:

The endpoint takes 30 seconds because the LLM is slow. How do you keep the API responsive?

Think first.

Student Answer:

"Make it asynchronous at the product level: accept the job, return a `task_id`, process it in a
worker, and let the client poll or get notified."

Tech Lead Correction:

Exactly.

```text
Synchronous endpoint  -> client waits 30s, connections pile up
Queue + worker + status -> API stays fast, work happens in the background
```

Production rule:

```text
Independent I/O -> gather()
Downstream limits -> semaphore + retry + backoff
Long jobs -> queue + workers + task status
```

---

# Mock Interview

## Architecture

Tech Lead Question:

Design an AI service that scrapes a page and summarizes it. Walk me through the architecture.

Student Thinking:

Identify layers, responsibilities, and dependencies.

Student Answer:

"A thin FastAPI router validates the request and delegates to a `SummaryService`. The service
orchestrates a `BrowserClient` to extract text, an `LLMClient` to summarize, and a
`TaskRepository` to persist. Dependencies are injected, the service is stateless, and each
layer depends on an interface."

Tech Lead Code Review:

Reject any design where the router calls OpenAI directly or the service writes SQL.

Production Discussion:

For volume, add a queue, a worker pool, semaphores, and retries with backoff.

Interview Answer:

"I separate transport, workflow, infrastructure, and persistence so the system is testable,
swappable, and scalable."

## Dependency Injection

Tech Lead Question:

Why inject dependencies instead of creating them inside the service?

Student Answer:

"To make the service testable and swappable. I can inject fakes in tests and switch providers
in production without changing the workflow."

Production Discussion:

FastAPI `Depends()` provides request-scoped injection.

Interview Answer:

"Dependency injection makes ownership explicit and decouples the service from concrete
implementations."

## Stateless and Shared State

Tech Lead Question:

Why must the service be stateless?

Student Answer:

"So concurrent requests do not share mutable state. Shared state causes data leaks and race
conditions and breaks horizontal scaling."

Production Discussion:

Keep request data in parameters and return values; use Redis for shared state that must
persist.

Interview Answer:

"Stateless services scale horizontally because any replica can serve any request."

## Throughput and Trade-off

Tech Lead Question:

Would you maximize concurrency to go faster?

Student Answer:

"No. I bound concurrency to the downstream bottleneck. Unlimited concurrency causes 429s,
timeouts, and pool exhaustion, which is slower overall."

Production Discussion:

Semaphore for bounding, retry with exponential backoff for 429s.

Interview Answer:

"I optimize for stable throughput, not maximum concurrency."

---

# English Interview

## Key Vocabulary

* layered architecture
* separation of concerns
* single responsibility
* low coupling / high cohesion
* dependency injection
* stateless service
* shared mutable state
* repository pattern
* interface-first design
* worker pool
* horizontal scaling
* throughput
* bottleneck
* exponential backoff
* trade-off

## Example Answer

I structure an AI backend in layers: a thin API, a stateless Service that orchestrates the
workflow, Browser and LLM infrastructure behind interfaces, and a Repository over the database.
Dependencies are injected, so the system is testable, swappable, and scalable.

## Beginner Questions

Question:

What is layered architecture?

Standard Answer:

Layered architecture separates a system into layers with single responsibilities — API,
Service, infrastructure, and persistence — so each can change independently.

Question:

What is dependency injection?

Standard Answer:

Dependency injection passes a component's dependencies from outside instead of creating them
inside, which improves testability and decoupling.

Question:

What is a stateless service?

Standard Answer:

A stateless service keeps no per-request mutable state on the instance, so any replica can
handle any request safely under concurrency.

## Intermediate Questions

Question:

Why keep FastAPI routers thin?

Standard Answer:

So HTTP concerns stay in the router and business logic lives in a reusable, testable service.
Fat routers duplicate logic and are hard to test.

Follow-up Question:

What belongs in `main.py`?

Question:

Why use the Repository pattern?

Standard Answer:

To hide the database behind methods so the service is not coupled to SQL and can be tested
without a real database.

Follow-up Question:

What should the repository return?

Question:

Why an LLM interface instead of calling a provider directly?

Standard Answer:

To support multiple providers, fail over, and mock the LLM in tests without changing the
workflow.

Follow-up Question:

How does multi-provider architecture improve reliability?

## Senior Questions

Question:

How do you scale an AI summarization service?

Standard Answer:

Async for per-worker I/O throughput, a queue and worker pool for capacity, semaphores per
downstream dependency, and retries with exponential backoff. I scale replicas horizontally
behind the queue.

Interview Review:

Strong answers separate concurrency (async) from parallelism (workers) and name the
bottleneck.

Production Case:

Summarizing 10,000 URLs is bounded by OpenAI rate limits, so I cap concurrency and back off on
429.

Question:

How do you keep a slow endpoint responsive?

Standard Answer:

Accept the job, return a `task_id`, process it in a worker, and expose task status. The API
stays fast while the work runs in the background.

Interview Review:

Look for queue + worker + status, not holding the connection.

Production Case:

A 30-second LLM job runs in a worker; the client polls `GET /tasks/{id}`.

Question:

What trade-off matters most in this design?

Standard Answer:

Stable throughput over maximum concurrency. Bounded concurrency is slower at peak but avoids
429s, timeouts, and pool exhaustion, which is faster and more reliable overall.

Interview Review:

Senior engineers argue trade-offs, not absolutes.

Production Case:

Capping concurrent OpenAI calls keeps latency predictable under load.

---

# Today's Takeaway

Day14 turns Day01–Day13 into a system.

```text
Ask always:
What is each layer's single responsibility?
What must this layer NOT do?
Which direction do dependencies point?
Where does state live?
Where is the bottleneck?
```

Today's core principles:

* A layered architecture separates transport, workflow, infrastructure, and persistence.
* Routers are thin; services orchestrate; repositories hide the database.
* Browser and LLM are infrastructure behind interfaces; they return data, not models.
* Dependency injection makes services stateless, testable, and swappable.
* Interface-first design means architecture before coding.
* Async gives per-worker throughput; workers and replicas give capacity.
* Semaphore, retry, and backoff protect downstream systems.
* Optimize for stable throughput and name your trade-offs.

The most important engineering sentence:

```text
Working once is a script; well-structured layers are a system.
```

---

# Before Next Lesson Checklist

Before Phase 2, confirm you can answer these without looking at the notes:

- [ ] Can I name the layers and each one's single responsibility?
- [ ] Can I say what each layer must NOT do?
- [ ] Why are FastAPI routers kept thin?
- [ ] Why must the service not contain HTTP or SQL logic?
- [ ] Why does the Browser layer return data, not FastAPI models?
- [ ] Why hide the LLM behind an interface?
- [ ] What problem does the Repository pattern solve?
- [ ] What is dependency injection and why does it help testing?
- [ ] Why must a service be stateless?
- [ ] What is the difference between async and worker scaling?
- [ ] How do Semaphore, retry, and backoff work together?
- [ ] How do I keep a slow endpoint responsive?
- [ ] Can I explain one architectural trade-off in English?
