# Lesson 6 — Decorators

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day05 — Closures

Next Lesson: Day07 — Iterators & Generators

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain why decorators exist.
* Explain decorators as functions that receive functions and return functions.
* Explain why `@decorator` is equivalent to `func = decorator(func)`.
* Explain why the wrapper function is the function that actually runs.
* Build universal decorators using `*args` and `**kwargs`.
* Explain why `functools.wraps` is required in production code.
* Explain metadata preservation for `__name__`, `__doc__`, `__annotations__`,
  and `inspect.signature`.
* Connect decorators to FastAPI route metadata, Playwright retry logic, and AI backend
  request tracing.
* Review decorator code like a tech lead.

---

# Why This Matters

Decorators matter because real backend systems have repeated behavior that does not belong
inside business logic.

Think first:

If every API endpoint needs logging, timing, authentication, retry, cache, and request
tracing, should every function manually write those same lines?

Junior answer:

Maybe we can just write the logging code inside every function.

Tech Lead response:

That works for two functions. It fails for two hundred.

The problem is not whether we can write logging code. The problem is whether repeated
engineering concerns stay consistent, testable, and easy to change.

These repeated concerns are called cross-cutting concerns.

Examples:

* logging
* timing
* retry
* authentication
* caching
* permission checks
* token tracking
* AI request tracing
* observability

They cut across many business functions.

Without decorators, code often becomes this:

```python
def create_user(name: str) -> dict[str, str]:
    start = time.perf_counter()
    logger.info("create_user started")

    user = {"name": name}

    elapsed = time.perf_counter() - start
    logger.info("create_user finished in %.4f seconds", elapsed)
    return user
```

The business logic is only this:

```python
user = {"name": name}
return user
```

The rest is infrastructure behavior.

Decorator thinking asks:

```text
Can we add infrastructure behavior around a function
without modifying the function's business code?
```

That is the reason decorators exist.

They let us enhance behavior while keeping business logic readable.

In FastAPI, decorators are not optional theory. Route handlers use decorators:

```python
@app.get("/users/{user_id}")
def read_user(user_id: int) -> dict[str, int]:
    return {"user_id": user_id}
```

In Playwright automation, decorators can wrap unstable browser steps with retry and timing.

In AI backend systems, decorators can track model latency, token usage, prompt metadata,
and tool-call behavior without polluting every AI function.

The classroom point:

```text
Decorator = clean business code + reusable engineering behavior.
```

---

# Roadmap Position

Day06 depends directly on Day05.

In Day05, we learned:

```text
Closure = Function Object + Captured Environment
```

Decorators are built on that idea.

```text
Day01: Functions are objects
        |
        v
Day03: Functions receive arguments and return values
        |
        v
Day05: Functions can return inner functions with captured environments
        |
        v
Day06: Decorators wrap functions with reusable behavior
        |
        v
FastAPI routes, Playwright retry tools, AI request tracing
```

Today's lesson is the bridge between Python function design and framework design.

If you understand decorators, FastAPI route decorators stop looking like magic.

If you understand wrappers, production logging and retry tools stop looking like magic.

If you understand `functools.wraps`, framework metadata bugs become much easier to debug.

Next lesson moves into iterators and generators. Decorators will still matter because many
backend frameworks combine decorators, callables, and lazy execution patterns.

---

# Lesson Map

```text
Today's Lesson

1. Why Decorators Matter
2. Cross-cutting Concerns
3. Decorator Mental Model
4. @decorator Syntax
5. Wrapper Function
6. Universal Decorators
7. functools.wraps
8. Production Patterns
9. FastAPI Connections
10. Playwright Connections
11. Interview Review
12. Today's Takeaway
```

---

# Estimated Study Time

Reading: 90-120 minutes

Exercises: 90-120 minutes

Coding: 60-90 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Main Concepts

## 1. Why Decorators Matter

Tech Lead question:

Why not just write logging code directly inside every function?

Think first.

The easy answer is:

```text
Because it is repetitive.
```

The engineering answer is deeper:

```text
Because repeated infrastructure logic creates inconsistent behavior,
larger functions, harder review, and higher production risk.
```

Imagine this codebase:

```python
def create_user(name: str) -> dict[str, str]:
    logger.info("start")
    user = {"name": name}
    logger.info("done")
    return user


def delete_user(user_id: int) -> dict[str, int]:
    logger.info("start")
    result = {"deleted": user_id}
    logger.info("done")
    return result
```

The logging format will eventually drift.

One function logs duration.

One forgets error logging.

One logs sensitive data.

One logs nothing.

The bug is not in Python syntax. The bug is in system design.

Decorators solve this class of problem by moving cross-cutting concerns out of business
functions.

```text
Business Function
        |
        v
Decorator adds reusable behavior around it
        |
        v
Business logic remains clean
```

Common cross-cutting concerns:

| Concern | Why it cuts across the system |
|---------|-------------------------------|
| Logging | Every important function needs observability |
| Timing | Latency must be measured consistently |
| Retry | External calls fail temporarily |
| Auth | Many endpoints require permission checks |
| Cache | Expensive operations often need reuse |
| Token tracking | AI systems need cost and usage visibility |
| Request tracing | Distributed systems need correlation IDs |

The key phrase:

```text
Decorators add behavior without modifying the business function.
```

## 2. Decorator Mental Model

A decorator is a function.

More specifically:

```text
Decorator = a function that receives a function and returns a function.
```

Example:

```python
def simple_decorator(func):
    def wrapper():
        print("before")
        result = func()
        print("after")
        return result

    return wrapper
```

This is not magic.

It is function object behavior from Day01 and closure behavior from Day05.

`func` is a function object.

`wrapper` is another function object.

The decorator returns `wrapper`.

ASCII model:

```text
original function
        |
        v
decorator(original function)
        |
        v
wrapper function
        |
        v
name now points to wrapper
```

## 3. `@decorator` Equals `func = decorator(func)`

This code:

```python
@simple_decorator
def hello():
    print("hello")
```

is equivalent to:

```python
def hello():
    print("hello")


hello = simple_decorator(hello)
```

That line is the heart of the lesson:

```python
hello = simple_decorator(hello)
```

It means the name `hello` no longer points directly to the original function.

It points to the returned `wrapper`.

Memory model:

```text
Before decoration

hello ───────────────> original hello function

After decoration

original hello function <──── captured by wrapper
                                 ^
                                 |
hello ───────────────────────> wrapper function
```

Classroom question:

When we call `hello()`, which function runs first?

Expected answer:

`wrapper` runs first.

Explanation:

The name `hello` now points to `wrapper`, not directly to the original function.

## 4. Wrapper Function

The wrapper is the function that actually gets called after decoration.

Example:

```python
def trace(func):
    def wrapper():
        print("before")
        result = func()
        print("after")
        return result

    return wrapper


@trace
def hello():
    print("hello")


hello()
```

Output:

```text
before
hello
after
```

Call flow:

```text
hello()
  |
  v
wrapper()
  |
  +--> print("before")
  |
  +--> original hello()
  |
  +--> print("after")
  |
  v
return result
```

Tech Lead question:

Why does `wrapper()` sometimes raise `TypeError`?

Consider:

```python
def trace(func):
    def wrapper():
        return func()

    return wrapper


@trace
def add(a: int, b: int) -> int:
    return a + b


add(1, 2)
```

This fails because `add` now points to `wrapper`, and `wrapper` accepts no arguments.

The runtime sees:

```text
wrapper(1, 2)
```

But the wrapper was defined as:

```python
def wrapper():
    ...
```

So Python raises `TypeError`.

This is not a decorator mystery. It is a function signature mismatch.

## 5. Universal Decorators

Production decorators almost always need to support different function signatures.

One function has no arguments.

One function has positional arguments.

One function has keyword arguments.

One function has both.

So the wrapper usually uses:

```python
*args
**kwargs
```

Universal template:

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def trace(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper
```

Why `*args`?

It forwards positional arguments.

Why `**kwargs`?

It forwards keyword arguments.

Why return the result?

Because the business function's return value must not be lost.

Bad decorator:

```python
def bad_timer(func):
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)

    return wrapper
```

This silently returns `None`.

Good decorator:

```python
def timer(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
```

Production rule:

```text
Forward arguments.
Return the result.
Preserve metadata.
Avoid changing business behavior accidentally.
```

## 6. `functools.wraps`

Now the most important production issue.

Without `functools.wraps`, the decorated function often looks like `wrapper`.

Example:

```python
def trace(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@trace
def create_user(name: str) -> dict[str, str]:
    """Create a user."""
    return {"name": name}


print(create_user.__name__)
```

Output:

```text
wrapper
```

Classroom reaction:

Why did `create_user` become `wrapper`?

Because after decoration, the name `create_user` points to the returned wrapper function.

That is technically correct but operationally dangerous.

Problems:

* Logs show `wrapper` instead of the real function name.
* Debugging becomes confusing.
* Documentation tools lose docstrings.
* Frameworks may lose annotations or signatures.
* `inspect.signature()` may show the wrong callable shape.

Production fix:

```python
from functools import wraps


def trace(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
```

Now metadata is preserved:

```python
print(create_user.__name__)         # create_user
print(create_user.__doc__)          # Create a user.
print(create_user.__annotations__)  # {'name': <class 'str'>, 'return': dict[str, str]}
```

Frameworks care about metadata.

FastAPI uses function metadata, annotations, and signatures to build routes, validation,
OpenAPI schemas, and dependency behavior.

If decorators destroy metadata, framework behavior can become confusing.

Tech Lead rule:

```text
In production Python, decorator without functools.wraps is suspicious by default.
```

## 7. Production Examples

### Logging Decorator

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def log_call(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        print(f"calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"finished {func.__name__}")
        return result

    return wrapper
```

In production code, use `logging`, not `print()`.

The classroom example uses `print()` so the call flow is visible.

### Timing Decorator

```python
import time
from collections.abc import Callable
from functools import wraps
from typing import Any


def measure_time(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started_at = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - started_at
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result

    return wrapper
```

### Retry Decorator

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def retry(times: int):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None

            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    last_error = error

            if last_error is not None:
                raise last_error

            raise RuntimeError("retry count must be at least 1")

        return wrapper

    return decorator
```

Notice the shape:

```text
retry(times)
        |
        v
decorator(func)
        |
        v
wrapper(*args, **kwargs)
```

This is a decorator factory.

### Authentication Decorator

Authentication is another cross-cutting concern.

Many functions need the same policy:

```text
Check permission before running business logic.
```

Example:

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def require_admin(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(user_role: str, *args: Any, **kwargs: Any) -> Any:
        if user_role != "admin":
            raise PermissionError("admin role required")

        return func(user_role, *args, **kwargs)

    return wrapper
```

Production warning:

Real authentication should usually be handled by framework dependency systems, middleware,
or well-reviewed security libraries.

The decorator example teaches the control-flow idea, not a complete security system.

### Cache Decorator

Caching is useful when a pure or stable function is expensive.

Example:

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def simple_cache(func: Callable[..., Any]) -> Callable[..., Any]:
    cache: dict[tuple[Any, ...], Any] = {}

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if kwargs:
            return func(*args, **kwargs)

        if args not in cache:
            cache[args] = func(*args, **kwargs)

        return cache[args]

    return wrapper
```

Tech Lead warning:

Caching is stateful. Ask:

* Is the function safe to cache?
* Can the result become stale?
* Can the cache grow forever?
* Does the cache key contain sensitive data?

### Token Tracking Decorator

AI backends need visibility into cost and usage.

Example:

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def track_tokens(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = func(*args, **kwargs)
        usage = result.get("usage", {})
        print(f"tokens={usage.get('total_tokens', 0)}")
        return result

    return wrapper
```

Production warning:

Track token counts and request IDs.

Do not log raw prompts by default.

### AI Request Tracing

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def trace_ai_request(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        print(f"ai_request_start function={func.__name__}")
        result = func(*args, **kwargs)
        print(f"ai_request_end function={func.__name__}")
        return result

    return wrapper
```

In a real AI backend, this can become structured logging:

* request id
* user id hash
* model name
* latency
* token count
* tool call count
* error type

Do not log raw prompts blindly.

Prompt data can contain private user information.

---

# Engineering Thinking

Decorators are not about making Python look clever.

They are about separating policy from business logic.

Policy:

* log every call
* measure latency
* retry temporary failures
* enforce authentication
* cache expensive results
* track AI token usage

Business logic:

* create user
* fetch page
* summarize document
* call model
* parse result

The engineering question is:

```text
Should this concern live inside one function,
or should it be applied consistently around many functions?
```

If the concern is repeated across many functions, decorators can be the right design.

## Code Review Thinking

What would a tech lead review?

* Does the decorator use `functools.wraps`?
* Does the wrapper forward `*args` and `**kwargs`?
* Does the wrapper return the original result?
* Does the decorator hide errors or log them properly?
* Does the decorator accidentally swallow exceptions?
* Does it log sensitive data?
* Does it preserve async behavior when wrapping async functions?
* Does it make business logic easier to read?

The key production risk:

```text
A decorator can quietly change every function it touches.
```

That is powerful.

That is also dangerous.

## Why FastAPI Cares About Metadata

FastAPI does a lot of reflection.

Reflection means the framework inspects Python objects at runtime.

FastAPI looks at:

* function name
* annotations
* parameters
* default values
* dependency markers
* return models

If a decorator turns everything into `wrapper(*args, **kwargs)`, FastAPI may lose useful
information.

That is why `functools.wraps` matters.

## AI Backend Thinking

AI systems often need request tracing, token tracking, and tool-call logging.

A bad design puts this logic inside every model call.

A better design wraps model calls with a decorator.

But production caution:

* Do not log full prompts by default.
* Do not leak user messages.
* Do not swallow model errors.
* Do not hide latency problems.
* Preserve metadata so debugging still names the real function.

---

# Classroom Exercises

## Exercise 1: What Does `@decorator` Mean?

Starter Code:

```python
def deco(func):
    def wrapper():
        print("wrapper")
        return func()

    return wrapper


@deco
def hello():
    print("hello")
```

Think First:

What is `hello` after decoration?

Expected Answer:

`hello` points to `wrapper`.

Explanation:

`@deco` is equivalent to:

```python
hello = deco(hello)
```

Follow-up Question:

Where is the original `hello` function preserved?

## Exercise 2: Output Prediction

Starter Code:

```python
def trace(func):
    def wrapper():
        print("A")
        func()
        print("B")

    return wrapper


@trace
def run():
    print("C")


run()
```

Think First:

Which function runs first?

Expected Output:

```text
A
C
B
```

Explanation:

`run` points to `wrapper`, so wrapper runs first and calls the original `run`.

Follow-up Question:

What happens if the wrapper does not call `func()`?

## Exercise 3: Why `wrapper()` Raises `TypeError`

Starter Code:

```python
def trace(func):
    def wrapper():
        return func()

    return wrapper


@trace
def add(a: int, b: int) -> int:
    return a + b


print(add(1, 2))
```

Think First:

Which callable receives `(1, 2)`?

Expected Output:

```text
TypeError
```

Explanation:

`add` now points to `wrapper`, and `wrapper` accepts no parameters.

Follow-up Question:

How do `*args` and `**kwargs` fix this?

## Exercise 4: Universal Decorator

Starter Code:

```python
def trace(func):
    def wrapper(*args, **kwargs):
        print("before")
        result = func(*args, **kwargs)
        print("after")
        return result

    return wrapper
```

Think First:

Why must the wrapper return `result`?

Expected Answer:

Because callers expect the decorated function to return the same value as the original
function.

Explanation:

A decorator should not accidentally change the function contract.

Follow-up Question:

What production bug happens if the wrapper forgets `return result`?

## Exercise 5: Metadata Without `wraps`

Starter Code:

```python
def trace(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@trace
def create_user(name: str) -> dict[str, str]:
    """Create a user."""
    return {"name": name}


print(create_user.__name__)
```

Think First:

What name will Python print?

Expected Output:

```text
wrapper
```

Explanation:

The decorated name points to the wrapper function.

Follow-up Question:

Why is this dangerous for logs and framework metadata?

## Exercise 6: Metadata With `functools.wraps`

Starter Code:

```python
from functools import wraps


def trace(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
```

Think First:

What metadata should `wraps` preserve?

Expected Answer:

Function name, docstring, annotations, and signature-related metadata.

Explanation:

`wraps` helps tools and frameworks understand the original function.

Follow-up Question:

Why does FastAPI care about function metadata?

## Exercise 7: Timer Decorator

Starter Code:

```python
import time
from functools import wraps


def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        started_at = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - started_at
        print(f"{func.__name__}: {elapsed:.4f}s")
        return result

    return wrapper
```

Think First:

What concern does this decorator extract from business logic?

Expected Answer:

Timing and latency measurement.

Explanation:

The business function no longer needs to manually measure its own runtime.

Follow-up Question:

What should replace `print()` in production code?

## Exercise 8: Playwright Retry Decorator

Starter Code:

```python
from functools import wraps


def retry_once(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            return await func(*args, **kwargs)

    return wrapper
```

Think First:

Why is this wrapper `async`?

Expected Answer:

Because Playwright's async API uses awaitable functions.

Explanation:

An async function must be wrapped by an async wrapper if the wrapper awaits it.

Follow-up Question:

What risks exist if retry catches every exception blindly?

## Exercise 9: AI Token Logger Decorator

Starter Code:

```python
from functools import wraps


def token_logger(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        print("record token usage here")
        return result

    return wrapper
```

Think First:

What should this decorator avoid logging?

Expected Answer:

Raw user prompts, private messages, credentials, and sensitive document content.

Explanation:

AI observability must balance debugging with privacy.

Follow-up Question:

Which fields are safer to log?

---

# FastAPI Connections

FastAPI uses decorators everywhere.

Example:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

The classroom mental model:

```text
@app.get("/health")
def health_check(...):
    ...
```

means:

```text
health_check = app.get("/health")(health_check)
```

`app.get("/health")` creates a decorator.

That decorator receives the route handler function.

FastAPI registers the function as a route.

Why does FastAPI rely on decorators?

* Route registration stays close to the function.
* The URL and HTTP method are visible above the handler.
* The business function remains a normal Python callable.
* FastAPI can inspect annotations and defaults.
* OpenAPI documentation can be generated from metadata.

Why `functools.wraps` matters:

FastAPI uses reflection.

If a custom decorator hides function metadata, FastAPI may see:

```text
wrapper(*args, **kwargs)
```

instead of:

```text
read_user(user_id: int)
```

That can affect documentation, validation, and debugging.

Production rule:

```text
When decorating FastAPI route handlers, preserve metadata and be careful with async.
```

AI Backend connection:

FastAPI endpoints often call AI services. Decorators can record latency, request IDs,
and token usage around endpoint logic, but they must not hide route metadata or leak
prompt content into logs.

---

# Playwright Connections

Playwright automation often needs retry, timing, and tracing.

Browser work is unstable because pages load slowly, selectors change, network calls fail,
and login sessions expire.

A decorator can wrap repeated operational behavior.

Example:

```python
from functools import wraps


def retry_once(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            return await func(*args, **kwargs)

    return wrapper
```

Usage:

```python
@retry_once
async def click_login_button(page):
    await page.get_by_role("button", name="Login").click()
```

Engineering warning:

Retry is not always safe.

Some operations are not idempotent.

Clicking "Pay" twice is not the same as clicking "Login" twice.

Tech Lead review:

* Is this operation safe to retry?
* Are exceptions logged?
* Is the retry count limited?
* Does the decorator preserve metadata?
* Does the wrapper remain async?
* Does it hide the real failure?

AI Backend connection:

If Playwright is part of an AI automation backend, decorators can trace browser steps,
latency, and failures. But they should avoid capturing global `Page` objects or shared
browser state.

---

# English Interview

## Key Vocabulary

* decorator
* wrapper function
* cross-cutting concern
* metadata preservation
* function object
* higher-order function
* reflection
* signature
* `functools.wraps`
* positional arguments
* keyword arguments

## Beginner Questions

### What is a decorator?

English answer:

A decorator is a function that takes another function and returns a new function, usually
to add reusable behavior around the original function.

Overseas interview answer:

In backend systems, I use decorators for cross-cutting concerns such as logging, timing,
authentication, retry, and tracing, so business logic stays clean.

### How does `@decorator` work?

English answer:

`@decorator` is syntax for `func = decorator(func)`. The original function is passed to
the decorator, and the function name is rebound to the returned function.

### What is wrapper?

English answer:

The wrapper is the returned function that runs when the decorated function is called. It
usually executes code before and after calling the original function.

### Why use decorators?

English answer:

Decorators avoid repeated infrastructure code and let us apply consistent behavior across
many functions without modifying the business logic.

## Intermediate Questions

### Why do decorators usually use `*args` and `**kwargs`?

English answer:

They allow the wrapper to accept and forward any positional and keyword arguments, so the
decorator can work with many different function signatures.

### What does `functools.wraps` do?

English answer:

`functools.wraps` preserves metadata from the original function, such as `__name__`,
`__doc__`, annotations, and signature-related information.

### Why does `@decorator` equal `func = decorator(func)`?

English answer:

Because decorator syntax is just syntactic sugar. Python creates the function object, passes
it to the decorator, and rebinds the original function name to the returned callable.

### Why does wrapper become the callable function?

English answer:

Because the decorator returns `wrapper`, and the original function name is rebound to that
returned wrapper.

## Senior Questions

### Explain the implementation of Python decorators.

English answer:

Decorators are higher-order functions. They receive a function object, usually define an
inner wrapper that captures the original function, and return that wrapper. The wrapper
then controls what happens before, during, and after the original function call.

### Explain metadata preservation.

English answer:

Metadata preservation means keeping the original function's name, docstring, annotations,
and signature information after decoration. This is important for debugging, logging,
documentation, and frameworks that use reflection.

### Why does FastAPI rely heavily on decorators?

English answer:

FastAPI uses decorators to register route handlers and keep route metadata close to the
function. It also inspects annotations and signatures to perform validation and generate
OpenAPI documentation.

### How do decorators improve maintainability in backend systems?

English answer:

Decorators centralize cross-cutting concerns. Instead of duplicating logging, timing,
retry, authentication, or tracing logic across many functions, we implement the concern
once and apply it consistently.

### Explain real production use cases of decorators in AI Backend.

English answer:

In AI backends, decorators can track latency, token usage, model calls, tool calls, cache
hits, and request IDs. They should avoid logging sensitive prompt content and should
preserve function metadata for debugging.

### Why are cross-cutting concerns implemented using decorators?

English answer:

Because cross-cutting concerns affect many functions but are not the core business logic
of those functions. Decorators let us apply these concerns consistently while keeping the
main function focused and readable.

---

# Today's Takeaway

Decorator thinking is backend engineering thinking.

The syntax is small:

```python
@decorator
def func():
    ...
```

The design idea is large:

```text
Add reusable behavior around a function
without modifying the business function.
```

The mental model:

```text
func = decorator(func)
```

The production template:

```python
from functools import wraps


def decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result

    return wrapper
```

The production warning:

```text
A decorator can quietly change every function it touches.
Use it carefully.
```

FastAPI uses decorators for route registration.

Playwright can use decorators for retry, timing, and tracing.

AI backends can use decorators for token tracking, request tracing, and model-call
observability.

---

# Before Next Lesson Checklist

Before Day07, confirm you can answer these without notes:

- [ ] What is a decorator?
- [ ] Why does Python need decorators?
- [ ] What is a cross-cutting concern?
- [ ] Why is `@decorator` equivalent to `func = decorator(func)`?
- [ ] Why does the wrapper function run first?
- [ ] Why does `wrapper()` raise `TypeError` when the original function needs arguments?
- [ ] Why do production decorators use `*args` and `**kwargs`?
- [ ] Why must a wrapper return the original result?
- [ ] What does `functools.wraps` preserve?
- [ ] Why does FastAPI care about metadata?
- [ ] How can decorators support Playwright retry logic?
- [ ] How can decorators support AI backend tracing?

---

# Best Practice

Use this as the default synchronous decorator shape:

```python
from collections.abc import Callable
from functools import wraps
from typing import Any


def my_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        return result

    return wrapper
```

Use this as the default async decorator shape:

```python
from collections.abc import Callable, Awaitable
from functools import wraps
from typing import Any


def my_async_decorator(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)
        return result

    return wrapper
```

Best practices:

* Use `functools.wraps`.
* Forward `*args` and `**kwargs`.
* Return the original result.
* Do not swallow exceptions silently.
* Do not log sensitive data.
* Keep decorator behavior small and predictable.
* Use async wrappers for async functions.
* Test decorated functions, not only decorators in isolation.

---

# Common Bugs

## Bug 1: Forgetting Arguments

```python
def deco(func):
    def wrapper():
        return func()

    return wrapper
```

This fails for functions that require parameters.

## Bug 2: Forgetting Return Value

```python
def deco(func):
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)

    return wrapper
```

The decorated function now returns `None`.

## Bug 3: Forgetting `functools.wraps`

Logs and debugging tools may show `wrapper` instead of the real function name.

## Bug 4: Swallowing Exceptions

```python
def unsafe(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            return None

    return wrapper
```

This hides real production failures.

## Bug 5: Wrong Async Wrapper

Wrapping an async function with a sync wrapper can return a coroutine without awaiting it.

---

# Code Review

A tech lead would reject a decorator if:

* It does not use `functools.wraps`.
* It loses return values.
* It fails on arguments.
* It catches broad exceptions without logging or re-raising.
* It logs raw user prompts or secrets.
* It changes function behavior without making that clear.
* It wraps async functions incorrectly.
* It makes debugging harder than the duplicated code it replaced.

Review question:

```text
Does this decorator make the system easier to reason about,
or does it hide too much behavior?
```

---

# Homework

## Mini Exercises

1. Explain `@decorator` using `func = decorator(func)`.
2. Predict decorator output order.
3. Fix a `TypeError` caused by `wrapper()`.
4. Write a universal decorator using `*args` and `**kwargs`.
5. Write a timer decorator.
6. Write a logging decorator.
7. Compare metadata with and without `functools.wraps`.
8. Explain why FastAPI route decorators need metadata.
9. Write a Playwright retry decorator.
10. Write an AI token logger decorator that avoids logging raw prompts.

## Repository Task

- [ ] Review `docs/python/day06-decorators.md`.
- [ ] Review decorator notes in `cheat_sheets/python.md`.
- [ ] Review Day06 interview questions in `interview/python.md`.
- [ ] Update progress tracking after review.
- [ ] Commit changes.
- [ ] Push to GitHub.
