# Lesson 12 — Context Managers

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day11 — Object-Oriented Programming

Next Lesson: Day13 — Async Programming

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain a Context Manager as a tool for deterministic resource cleanup, not just `with` syntax.
* Explain the Resource Lifecycle: Acquire -> Use -> Release.
* Explain why business logic should not own resource management.
* Explain `with`, `try/finally`, `__enter__`, and `__exit__`.
* Explain how `__exit__` participates in exception handling.
* Explain `yield` vs `return` and generator pause/resume inside `@contextmanager`.
* Connect context managers to FastAPI `yield` dependencies, Playwright cleanup, and AI backend resource cleanup.
* Identify production resource-leak bugs.
* Answer beginner, intermediate, and senior interview questions.

---

# Why This Matters

Context Managers are not about the `with` keyword looking clean.

Context Managers exist because production systems acquire resources that must be released deterministically.

Tech Lead Question:

When a backend holds a database connection, a file handle, or a browser context, what is the
most dangerous moment?

Think first.

Student Answer:

"The moment something goes wrong in the middle, because the cleanup code might never run."

Tech Lead Explanation:

Exactly.

The hard part of resource management is not acquiring the resource.

The hard part is releasing it **every time**, including when an exception is raised.

```text
Acquire
   |
   v
Use   <-- exception can happen here
   |
   v
Release  <-- must still happen
```

This is the core idea of Day12:

```text
Resource Lifecycle = Acquire -> Use -> Release
```

A Context Manager guarantees the Release step runs whether the Use step succeeds or fails.

In FastAPI, a request opens a database session that must be closed after the response.

In Playwright, a job opens a `BrowserContext` that must be closed after the job.

In AI backend systems, a request may open an LLM stream, a Redis connection, or a lock that
must be released even when generation fails halfway.

The goal is not:

```text
memorize the with statement
```

The goal is:

```text
guarantee deterministic cleanup so production resources never leak
```

Why before How.

If you only learn the syntax, you will still write leaking code.

If you learn the lifecycle, you will design systems that clean up correctly under failure.

---

# Roadmap Position

Day11 taught objects and responsibility ownership.

Day12 teaches how an object can own a resource's **lifecycle** and guarantee its cleanup.

```text
Day11: Object-Oriented Programming
        |
        v
Day12: Context Managers
        |
        v
Day13: Async Programming
        |
        v
FastAPI dependency cleanup
        |
        v
Playwright context cleanup
        |
        v
AI backend resource cleanup
```

Day08 taught exception handling.

Day07 taught generators, pause, and resume.

Day12 combines both:

```text
Exception Handling (Day08)
        +
Generator Pause / Resume (Day07)
        |
        v
Context Manager cleanup guarantee
```

This is why Day12 sits exactly here.

You need objects, exceptions, and generators before you can fully understand context managers.

```text
Object Ownership
      |
      v
Resource Lifecycle
      |
      v
Deterministic Cleanup
```

---

# Lesson Map

```text
Today's Lesson

1. Why Deterministic Cleanup Matters
2. Resource Lifecycle: Acquire -> Use -> Release
3. try / finally
4. The with Statement
5. Context Manager Protocol: __enter__ / __exit__
6. Exception Handling in __exit__
7. @contextmanager and yield vs return
8. Generator Pause / Resume Cleanup Model
9. Production Risks and Resource Leaks
10. FastAPI Connections
11. Playwright Connections
12. AI Backend Connections
13. Interview Review
```

---

# Estimated Study Time

```text
Reading: 90-120 minutes
Exercises: 60-90 minutes
Coding: 45-60 minutes
Review: 30-45 minutes

Total: 4-5 hours
```

---

# Main Concepts

## Concept 1: Resource Lifecycle

Every resource follows the same lifecycle.

```text
Acquire
   |
   v
Use
   |
   v
Release
```

Examples of resources:

```text
File handle
Database connection
Database session
Redis connection
Lock
BrowserContext
LLM stream
```

Tech Lead Question:

Why is Release the step engineers forget most often?

Think first.

Student Answer:

"Because Acquire and Use are the visible work. Release is easy to skip, especially when an
error happens before we reach it."

Tech Lead Explanation:

Correct.

Release is the step that fails silently.

The system keeps running, but resources slowly leak until the server runs out of connections,
file handles, or memory.

Production Risk:

```text
Forgotten Release
      |
      v
Resource Leak
      |
      v
Exhaustion under load
```

The whole point of a Context Manager is to make Release automatic and guaranteed.

## Concept 2: `try / finally`

Before Context Managers, `try / finally` is the manual way to guarantee cleanup.

```python
f = open("data.txt")
try:
    data = f.read()
finally:
    f.close()
```

Mental model:

```text
open        -> Acquire
try block   -> Use
finally     -> Release (always runs)
```

Tech Lead Question:

Why put `f.close()` in `finally` instead of after `f.read()`?

Think first.

Student Answer:

"Because if `f.read()` raises an exception, code after it never runs, but `finally` still runs."

Tech Lead Explanation:

Exactly.

`finally` runs whether the `try` block succeeds or raises.

```text
Use succeeds -> finally runs
Use fails     -> finally runs
```

This guarantees Release.

Common Mistake:

```python
f = open("data.txt")
data = f.read()
f.close()   # never runs if read() raises
```

If `read()` raises, `close()` is skipped and the file handle leaks.

`try / finally` is correct but verbose.

The `with` statement is the cleaner tool built on top of the same guarantee.

## Concept 3: The `with` Statement

`with` is syntax that runs Acquire, then Use, then Release automatically.

```python
with open("data.txt") as f:
    data = f.read()
```

This is equivalent to:

```python
f = open("data.txt")
try:
    data = f.read()
finally:
    f.close()
```

Mental model:

```text
with open(...) as f:   -> Acquire (__enter__)
    body               -> Use
                       -> Release (__exit__) always runs
```

Tech Lead Question:

What does `with` guarantee that a plain assignment does not?

Think first.

Student Answer:

"That the Release step runs even if the body raises an exception."

Tech Lead Explanation:

Correct.

`with` turns a two-step manual pattern into one safe block.

The object after `with` must be a **Context Manager**.

That is the object that knows how to Acquire and Release itself.

## Concept 4: Context Manager Protocol

A Context Manager is any object that implements two methods:

```text
__enter__  -> Acquire, returns the resource
__exit__   -> Release, always called
```

```python
class FileManager:
    def __init__(self, path: str) -> None:
        self.path = path
        self.file = None

    def __enter__(self):
        self.file = open(self.path)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.file.close()
        return False
```

Usage:

```python
with FileManager("data.txt") as f:
    data = f.read()
```

Execution flow:

```text
with FileManager(...) as f
        |
        v
__enter__()      -> Acquire, return resource
        |
        v
body runs        -> Use
        |
        v
__exit__()       -> Release, always runs
```

Tech Lead Question:

Why does `__enter__` return the resource instead of the manager?

Think first.

Student Answer:

"So the `as f` name points to the usable resource, not the wrapper object."

Tech Lead Explanation:

Exactly.

`__enter__` returns whatever should be bound to the `as` name.

`__exit__` receives exception information so it can decide what to do during cleanup.

## Concept 5: Exception Handling in `__exit__`

`__exit__` receives three arguments:

```text
exc_type   -> exception class, or None
exc_value  -> exception instance, or None
traceback  -> traceback object, or None
```

If the body succeeds:

```text
exc_type = None
exc_value = None
traceback = None
```

If the body raises:

```text
exc_type = ValueError
exc_value = ValueError("bad input")
traceback = <traceback>
```

Return value rule:

```text
__exit__ returns False -> exception propagates (normal)
__exit__ returns True  -> exception is suppressed (silenced)
```

```python
class FileManager:
    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.file.close()   # Release always runs
        return False        # do not hide errors
```

Tech Lead Question:

Should a Context Manager usually return `True` from `__exit__`?

Think first.

Student Answer:

"No. Returning `True` hides exceptions. We usually want cleanup to run but errors to still
propagate."

Tech Lead Explanation:

Correct.

The key insight:

```text
Cleanup should always run.
Errors should usually still propagate.
```

Release happens regardless.

Suppressing the error is a rare, deliberate decision.

Common Mistake:

Returning `True` by accident and silently swallowing production errors.

## Concept 6: `@contextmanager` and `yield`

Writing `__enter__` and `__exit__` is verbose.

Python offers a generator-based shortcut:

```python
from contextlib import contextmanager


@contextmanager
def open_file(path: str):
    f = open(path)          # Acquire
    try:
        yield f             # Use (pause here, hand resource to body)
    finally:
        f.close()           # Release (always runs on resume)
```

Usage:

```python
with open_file("data.txt") as f:
    data = f.read()
```

This is where Day07 returns.

`yield` is not `return`.

```text
return -> function ends, nothing resumes
yield  -> function pauses, can resume later
```

The generator pauses at `yield`, the body runs, then the generator resumes and runs the
`finally` cleanup.

Generator cleanup model:

```text
Enter
   |
   v
code before yield   -> Acquire
   |
   v
yield               -> Pause, hand resource to body
   |
   v
Business Logic      -> Use
   |
   v
Resume              -> generator continues after yield
   |
   v
finally             -> Release
   |
   v
Cleanup
```

Tech Lead Question:

Why must the `yield` sit inside `try / finally`?

Think first.

Student Answer:

"Because if the body raises, the exception is thrown back into the generator at the `yield`.
The `finally` guarantees cleanup still runs."

Tech Lead Explanation:

Exactly.

When the body raises, the exception is re-raised at the `yield` point.

Without `try / finally`, the code after `yield` would be skipped and the resource would leak.

```text
body raises
   |
   v
exception thrown into generator at yield
   |
   v
finally still runs
   |
   v
Release guaranteed
```

Common Mistake:

```python
@contextmanager
def bad_open(path: str):
    f = open(path)
    yield f
    f.close()   # skipped if body raises
```

Without `try / finally`, this leaks on failure.

## Concept 7: `yield` vs `return`

| Keyword | Behavior | Cleanup |
|---------|----------|---------|
| `return` | Function ends immediately | No resume, no post-cleanup step |
| `yield` | Function pauses and can resume | Code after `yield` runs on resume |

In a context manager:

```text
Code before yield -> Acquire
yield              -> Use
Code after yield   -> Release
```

`return` cannot express this pattern because it has no "after" phase.

This is why `@contextmanager` relies on `yield`, not `return`.

---

# Engineering Thinking

## Business Logic Should Not Own Resource Management

A core Day12 principle:

```text
Business Logic should not own Resource Management.
```

Bad design mixes them:

```python
def handle_request():
    conn = connect_db()
    result = run_query(conn)   # if this raises, conn leaks
    conn.close()
    return result
```

Good design separates them:

```python
def handle_request():
    with get_connection() as conn:   # resource management
        return run_query(conn)       # business logic
```

Tech Lead Question:

Why is separating these two concerns valuable?

Think first.

Student Answer:

"Because business logic changes often, and we do not want cleanup correctness to depend on
remembering to close things in every code path."

Tech Lead Explanation:

Exactly.

The Context Manager separates concerns:

```text
Context Manager  -> owns Acquire and Release
Business Logic   -> owns the Use step only
```

The business code can raise, return early, or branch, and cleanup is still guaranteed.

## Composition with Framework Lifecycle

Context Managers compose with framework lifecycles.

FastAPI, Playwright, and AI backends each define **when** work starts and ends.

A Context Manager plugs Release into that lifecycle boundary.

```text
Framework defines the boundary
        |
        v
Context Manager guarantees cleanup at the boundary
```

This is why FastAPI dependencies, Playwright jobs, and AI request handlers all use this
pattern.

## Production Risks

Missing cleanup causes real production failures:

| Leak | Cause | Impact |
|------|-------|--------|
| Database connection leak | Connection not returned to pool | Pool exhaustion, requests hang |
| File handle leak | File never closed | "Too many open files" errors |
| BrowserContext leak | Playwright context not closed | Memory growth, zombie browsers |
| Redis connection leak | Connection not released | Connection pool exhaustion |
| LLM stream leak | Stream not closed on failure | Hanging sockets, wasted tokens |
| Lock not released | `finally` missing | Deadlock, stuck workers |

Tech Lead Question:

Which of these leaks is hardest to detect in development?

Think first.

Student Answer:

"The ones that only appear under load or under failure, like connection pool exhaustion.
They pass local tests but fail in production."

Tech Lead Explanation:

Correct.

Leaks are dangerous precisely because they are invisible until scale or failure exposes them.

Context Managers remove the entire class of "forgot to release" bugs.

## Tech Lead Review Checklist

A tech lead reviewing resource code asks:

* Is every resource acquired with `with` or `try / finally`?
* Does cleanup run on the failure path, not only the success path?
* Does `__exit__` accidentally return `True` and hide errors?
* In `@contextmanager`, is `yield` wrapped in `try / finally`?
* Does the business logic own cleanup it should not own?
* Are FastAPI `yield` dependencies closing sessions correctly?
* Are Playwright contexts closed per job?

## CTO Thinking

At system level, deterministic cleanup affects:

```text
Reliability   -> no slow resource exhaustion
Scalability   -> connection pools stay healthy under load
Cost          -> no leaked LLM streams burning tokens
Maintainability -> cleanup is centralized, not scattered
```

Bad cleanup does not crash immediately.

It degrades the system slowly, which is harder to diagnose and more expensive to fix.

---

# Classroom Exercises

## Level 1: `with`

Question:

Rewrite this file read using `with`.

Think First:

What happens to `close()` if `read()` raises?

Starter Code:

```python
f = open("data.txt")
data = f.read()
f.close()
```

Expected Output:

```python
with open("data.txt") as f:
    data = f.read()
```

Explanation:

`with` guarantees the file is closed even if `read()` raises.

Follow-up Question:

What method does `with` call to close the file automatically?

## Level 2: `try / finally`

Question:

Guarantee cleanup without `with`.

Think First:

Which block always runs?

Starter Code:

```python
conn = connect_db()
result = run_query(conn)
conn.close()
```

Expected Output:

```python
conn = connect_db()
try:
    result = run_query(conn)
finally:
    conn.close()
```

Explanation:

`finally` runs on both success and failure, so the connection is always released.

Follow-up Question:

Why is this safer than closing after `run_query(conn)`?

## Level 3: `__enter__`

Question:

Implement `__enter__` so `as f` receives the file.

Think First:

What should `__enter__` return?

Starter Code:

```python
class FileManager:
    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self):
        ...
```

Expected Output:

```python
def __enter__(self):
    self.file = open(self.path)
    return self.file
```

Explanation:

`__enter__` acquires the resource and returns what the `as` name should point to.

Follow-up Question:

Why return the file instead of `self`?

## Level 4: `__exit__`

Question:

Implement `__exit__` so the file always closes.

Think First:

What three arguments does `__exit__` receive?

Starter Code:

```python
class FileManager:
    def __exit__(self, exc_type, exc_value, traceback):
        ...
```

Expected Output:

```python
def __exit__(self, exc_type, exc_value, traceback) -> bool:
    self.file.close()
    return False
```

Explanation:

`__exit__` releases the resource. Returning `False` lets any exception propagate.

Follow-up Question:

What happens if `__exit__` returns `True`?

## Level 5: Exception Cleanup

Question:

Predict whether cleanup runs when the body raises.

Think First:

Does `__exit__` run on failure?

Starter Code:

```python
class Managed:
    def __enter__(self):
        print("acquire")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("release")
        return False


with Managed():
    print("use")
    raise ValueError("boom")
```

Expected Output:

```text
acquire
use
release
ValueError: boom
```

Explanation:

`__exit__` runs before the exception propagates, so cleanup happens even on failure.

Follow-up Question:

How would you suppress the `ValueError`?

## Level 6: `yield`

Question:

Write a context manager using `@contextmanager`.

Think First:

Where do Acquire, Use, and Release go relative to `yield`?

Starter Code:

```python
from contextlib import contextmanager


@contextmanager
def open_file(path: str):
    ...
```

Expected Output:

```python
@contextmanager
def open_file(path: str):
    f = open(path)
    try:
        yield f
    finally:
        f.close()
```

Explanation:

Code before `yield` acquires, the `yield` hands the resource to the body, and `finally`
guarantees release on resume.

Follow-up Question:

Why must `yield` sit inside `try / finally`?

## Level 7: FastAPI Dependency

Question:

Write a FastAPI-style database dependency that always closes the session.

Think First:

What guarantees `db.close()` runs after the response?

Starter Code:

```python
def get_db():
    ...
```

Expected Output:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Explanation:

FastAPI resumes the generator after the response is sent, and `finally` closes the session.

Follow-up Question:

Why does FastAPI use `yield` here instead of `return`?

---

# FastAPI Connections

FastAPI uses the context manager pattern directly in dependencies.

## `yield` Dependencies

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Usage:

```python
from fastapi import Depends


@app.get("/users")
def list_users(db=Depends(get_db)):
    return db.query(User).all()
```

Request lifecycle:

```text
Request
   |
   v
Create Session      -> Acquire (code before yield)
   |
   v
yield db            -> hand session to handler
   |
   v
Business Logic      -> Use (route handler runs)
   |
   v
Resume Generator    -> FastAPI resumes after response
   |
   v
db.close()          -> Release (finally)
```

Why FastAPI uses this design:

* The session is request-scoped.
* Cleanup is guaranteed even if the handler raises.
* The route handler owns business logic, not resource management.

What a production engineer should watch for:

* Never share one session across requests.
* Always close in `finally`, not after `yield`.
* Do not swallow exceptions during cleanup.

## Lifespan and Startup / Shutdown

FastAPI also uses context managers for application lifespan:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    # startup: acquire shared resources
    yield
    # shutdown: release shared resources
```

Same lifecycle idea at application scale:

```text
Startup   -> Acquire
Serving   -> Use
Shutdown  -> Release
```

---

# Playwright Connections

Playwright resources must be released per job.

## Context Cleanup

```python
async def run_job(browser):
    context = await browser.new_context()   # Acquire
    try:
        page = await context.new_page()
        await page.goto("https://example.com")
        # Use
    finally:
        await context.close()               # Release
```

Object ownership:

```text
Browser         -> shared, long-lived
BrowserContext  -> per job, must be closed
Page            -> lives inside the context
```

Why cleanup matters here:

* A `BrowserContext` holds cookies, local storage, and session state.
* If it is not closed, memory grows and zombie browser processes accumulate.
* Under many jobs, leaked contexts exhaust system memory.

Production rule:

```text
Share the Browser.
Isolate the BrowserContext per job.
Always close the context in finally.
```

Playwright's own API is a context manager:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    # Use
    browser.close()
```

`with sync_playwright()` guarantees the driver process is cleaned up.

---

# AI Backend Connections

AI backend requests acquire several resources that must be released.

## Resources That Leak in AI Backends

```text
LLM stream
Redis connection
Database session
Vector store client
Concurrency lock
```

## LLM Stream Cleanup

```python
from contextlib import contextmanager


@contextmanager
def llm_stream(client, prompt: str):
    stream = client.stream(prompt)   # Acquire
    try:
        yield stream                 # Use
    finally:
        stream.close()               # Release, even if generation fails
```

Why this matters:

* An LLM stream holds an open network connection.
* If the client disconnects or generation raises, the stream must still close.
* A leaked stream keeps a socket open and can keep billing tokens.

## Lock Cleanup

```python
def process_job(lock):
    with lock:            # Acquire
        do_work()         # Use
                          # Release automatic, even on failure
```

If a lock is acquired without a context manager and the work raises, the lock is never
released and workers deadlock.

## Composition Example

```python
def handle_chat(request):
    with get_db() as db, get_redis() as cache:
        with llm_stream(client, request.prompt) as stream:
            return build_response(db, cache, stream)
```

Multiple resources, each with guaranteed cleanup:

```text
Acquire db
Acquire cache
Acquire stream
        |
        v
Use (build_response)
        |
        v
Release stream
Release cache
Release db
```

Cleanup runs in reverse acquisition order, and every layer is released even if
`build_response` raises.

---

# English Interview

## Key Vocabulary

* context manager
* resource lifecycle
* acquire
* release
* cleanup
* `__enter__`
* `__exit__`
* `with` statement
* `try / finally`
* deterministic cleanup
* resource leak
* connection pool
* `yield` dependency

## Example Answer

In Python, a context manager guarantees that a resource is released after use, even if an
error occurs. It implements `__enter__` to acquire the resource and `__exit__` to release it.
The `with` statement calls both automatically, so cleanup is deterministic. In FastAPI, a
database dependency uses `yield` so the session is created before the request and closed
after it.

## Beginner Questions

Question:

What is a context manager?

Standard Answer:

A context manager is an object that defines setup and cleanup behavior, usually acquiring a
resource in `__enter__` and releasing it in `__exit__`, so cleanup is guaranteed.

Question:

Why use `with`?

Standard Answer:

`with` guarantees that cleanup runs even if the body raises an exception, which prevents
resource leaks and removes manual `close()` calls.

Question:

What are `__enter__` and `__exit__`?

Standard Answer:

`__enter__` acquires the resource and returns what the `as` name points to. `__exit__` runs
afterward to release the resource and can receive exception information.

## Intermediate Questions

Question:

Explain the resource lifecycle.

Standard Answer:

Every resource follows Acquire, Use, and Release. The dangerous step is Release, because it
can be skipped when an exception happens during Use. Context managers guarantee Release.

Follow-up Question:

How does `try / finally` express this lifecycle?

Question:

What is the difference between `yield` and `return` in a context manager?

Standard Answer:

`return` ends the function with no resume, so there is no place for cleanup after the body.
`yield` pauses the function, hands the resource to the body, and resumes afterward to run the
`finally` cleanup.

Follow-up Question:

Why must `yield` be inside `try / finally`?

Question:

Explain the FastAPI dependency lifecycle.

Standard Answer:

A FastAPI `yield` dependency creates a resource before the request, yields it to the handler,
and resumes after the response to close it in `finally`. The session is request-scoped and
always cleaned up.

Follow-up Question:

Why should the session not be shared across requests?

## Senior Questions

Question:

How do you guarantee production cleanup under failure?

Standard Answer:

I acquire every resource with a context manager or `try / finally`, put release in `finally`,
and avoid returning `True` from `__exit__` so errors still propagate. This guarantees release
on both success and failure paths.

Follow-up Question:

When would you deliberately suppress an exception in `__exit__`?

Production Case:

A database session dependency must close in `finally`; otherwise a failing query leaks a
connection and eventually exhausts the pool.

Question:

How do context managers apply to FastAPI?

Standard Answer:

FastAPI uses `yield` dependencies and `asynccontextmanager` lifespan handlers. Both follow
Acquire -> Use -> Release, with cleanup guaranteed at the request or application boundary.

Production Case:

`get_db` yields a session and closes it in `finally` so every request cleans up its own
connection.

Question:

How do context managers apply to Playwright?

Standard Answer:

Playwright shares a `Browser` but isolates a `BrowserContext` per job. Each context must be
closed in `finally` to avoid memory growth and session-state leaks between jobs.

Production Case:

A worker that forgets to close contexts slowly leaks memory and leaves zombie browser
processes.

Question:

How do context managers apply to AI backends?

Standard Answer:

AI requests acquire LLM streams, Redis connections, database sessions, and locks. Each must
be released even when generation fails, so I wrap them in context managers to prevent socket,
connection, and lock leaks.

Production Case:

A leaked LLM stream keeps a socket open and can keep consuming tokens after the client
disconnects.

Question:

Explain resource ownership in cleanup design.

Standard Answer:

Business logic should not own resource management. The context manager owns Acquire and
Release, and the business logic owns only the Use step. This separation keeps cleanup correct
even as business code changes.

Follow-up Question:

Why is mixing business logic and cleanup a maintainability risk?

---

# Today's Takeaway

Context Managers are not about the `with` keyword.

They are about guaranteeing deterministic cleanup.

```text
Resource Lifecycle
      |
      +-- Acquire
      +-- Use
      +-- Release  (always guaranteed)
```

Today's core principles:

* Every resource follows Acquire -> Use -> Release.
* Release is the step engineers forget, especially on failure.
* `try / finally` guarantees cleanup manually.
* `with` guarantees cleanup automatically.
* `__enter__` acquires; `__exit__` releases and sees exceptions.
* `__exit__` returning `True` suppresses errors and is usually wrong.
* `@contextmanager` uses `yield` because it needs a resume phase for cleanup.
* `yield` must sit inside `try / finally`.
* Business logic should not own resource management.
* FastAPI, Playwright, and AI backends all rely on this cleanup guarantee.

The most important engineering sentence:

```text
Cleanup should always run; errors should usually still propagate.
```

---

# Before Next Lesson Checklist

Before Day13, confirm you can answer these without looking at the notes:

- [ ] What is the resource lifecycle?
- [ ] Why is Release the dangerous step?
- [ ] How does `try / finally` guarantee cleanup?
- [ ] What does `with` guarantee that plain code does not?
- [ ] What do `__enter__` and `__exit__` do?
- [ ] What three arguments does `__exit__` receive?
- [ ] What happens when `__exit__` returns `True` vs `False`?
- [ ] Why does `@contextmanager` use `yield` instead of `return`?
- [ ] Why must `yield` sit inside `try / finally`?
- [ ] Why should business logic not own resource management?
- [ ] How does a FastAPI `yield` dependency clean up a session?
- [ ] Why must a Playwright `BrowserContext` be closed per job?
- [ ] What resources leak in AI backends and how do context managers prevent it?
- [ ] Can I explain deterministic cleanup in an interview in English?
