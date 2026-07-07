# Python Cheat Sheet

## Purpose

One-page Python interview review sheet for AI Backend Engineer preparation.

---

## Core Mental Model

```text
Name -> Reference -> Object
```

Every object has:

- identity
- type
- value

---

## `==` vs `is`

```python
a == b  # value equality
a is b  # object identity
```

Use:

```python
if value is None:
    ...

if status == "active":
    ...
```

Never use `is` for string or number value comparison.

---

## Mutable Default Argument

Bad:

```python
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items
```

Good:

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

Reason:

Default arguments are evaluated once at function definition time.

---

## Mutable vs Immutable

Mutable objects can change after creation.

Examples:

- `list`
- `dict`
- `set`

Immutable objects cannot change after creation.

Examples:

- `int`
- `float`
- `str`
- `bool`
- `tuple`, if all nested values are hashable

Core rule:

```text
Assignment changes what a name points to.
Mutation changes the object itself.
```

---

## Reference Assignment

```python
a = [1, 2]
b = a
b.append(3)

print(a)      # [1, 2, 3]
print(a is b) # True
```

`b = a` does not copy the list.

It binds `b` to the same list object.

Use `id()` to verify identity during learning:

```python
print(id(a) == id(b))  # True
```

---

## `append()` vs `+=` vs `a = a + [...]`

| Operation | Behavior | `id(a)` changes? | Other references see change? |
|-----------|----------|------------------|-------------------------------|
| `a.append(3)` | Mutates list in place | No | Yes |
| `a += [3]` | Mutates list in place | No | Yes |
| `a = a + [3]` | Creates new list and rebinds `a` | Yes | No |

Example:

```python
a = [1, 2]
b = a
a = a + [3]

print(a)  # [1, 2, 3]
print(b)  # [1, 2]
```

```python
a = [1, 2]
b = a
a += [3]

print(a)  # [1, 2, 3]
print(b)  # [1, 2, 3]
```

---

## Shallow Copy vs Deep Copy

| Copy type | What is copied? | Nested objects shared? | Use when |
|-----------|------------------|-------------------------|----------|
| `copy.copy()` | First layer | Yes | Outer container isolation is enough |
| `copy.deepcopy()` | Full object tree | No | Full isolation is required |

Shallow copy example:

```python
import copy

original = [["python"]]
cloned = copy.copy(original)
cloned[0].append("fastapi")

print(original)  # [['python', 'fastapi']]
```

Deep copy example:

```python
import copy

original = [["python"]]
cloned = copy.deepcopy(original)
cloned[0].append("fastapi")

print(original)  # [['python']]
```

---

## Hashable vs Unhashable

Hashable objects can be dictionary keys.

Unhashable objects cannot.

| Object | Hashable? | Reason |
|--------|-----------|--------|
| `str` | Yes | Immutable |
| `int` | Yes | Immutable |
| `tuple` | Sometimes | Only if all nested values are hashable |
| `list` | No | Mutable |
| `dict` | No | Mutable |
| `set` | No | Mutable |

Valid:

```python
cache = {("user", 1): "active"}
```

Invalid:

```python
cache = {["user", 1]: "active"}
```

Also invalid:

```python
cache = {("user", [1, 2]): "active"}
```

Reason:

The tuple contains a list, and the list is unhashable.

---

## Function Parameter Passing

Python passes object references by value.

This model is also called call by sharing.

Core rule:

```text
Function parameters are local names.
They point to the same objects passed by the caller.
```

Example:

```python
def add_item(items: list[int]) -> None:
    items.append(3)


values = [1, 2]
add_item(values)

print(values)  # [1, 2, 3]
```

Why:

`items` and `values` point to the same list object.

---

## Mutation vs Rebinding

Mutation changes the object.

Rebinding changes what a local name points to.

| Operation | Caller sees change? | Reason |
|-----------|---------------------|--------|
| `items.append(3)` | Yes | Mutates shared list |
| `items += [3]` | Yes | Mutates shared list |
| `items = items + [3]` | No | Rebinds local name |
| `items = [1, 2, 3]` | No | Rebinds local name |

Example:

```python
def add_with_plus(items: list[int]) -> None:
    items = items + [3]


values = [1, 2]
add_with_plus(values)

print(values)  # [1, 2]
```

If a function creates a new object, return it:

```python
def add_with_return(items: list[int]) -> list[int]:
    return items + [3]
```

---

## Mutable vs Immutable in Function Calls

Mutable arguments can be changed in place:

```python
def add_role(user: dict[str, str]) -> None:
    user["role"] = "admin"
```

Immutable arguments cannot be changed in place:

```python
def increment(value: int) -> None:
    value = value + 1
```

The `increment()` function only rebinds the local name `value`.

---

## Common Mutable Methods

These methods usually mutate in place:

| Type | Methods |
|------|---------|
| `list` | `append`, `extend`, `insert`, `remove`, `pop`, `sort`, `reverse`, `clear` |
| `dict` | `update`, `setdefault`, `pop`, `clear` |
| `set` | `add`, `update`, `remove`, `discard`, `clear` |

Interview warning:

```text
If a function calls one of these methods on a parameter,
it may change caller-visible state.
```

---

## Scope & LEGB

Python name lookup follows LEGB:

```text
Local -> Enclosing -> Global -> Built-in
```

Meaning:

- Local: current function scope
- Enclosing: outer function scopes
- Global: module scope
- Built-in: Python built-ins such as `len`, `print`, `dict`

Python uses lexical scope:

```text
A function searches names based on where it is defined,
not where it is called.
```

---

## `global`

`global` tells Python to bind a name in module global scope.

```python
count = 0


def add() -> None:
    global count
    count += 1
```

Use rarely.

Backend rule:

```text
Do not store request state in global variables.
```

---

## `nonlocal`

`nonlocal` tells Python to bind a name in the nearest enclosing function scope.

```python
def outer():
    count = 0

    def inner():
        nonlocal count
        count += 1
        return count

    return inner
```

Use when closure state must be rebound intentionally.

---

## Closure

Engineering definition:

```text
Closure = Function Object + Captured Environment
```

Example:

```python
def make_counter():
    count = 0

    def counter():
        nonlocal count
        count += 1
        return count

    return counter
```

The returned function keeps access to `count` even after `make_counter()` returns.

Closure is not just "a function inside another function."

The important part is:

```text
The inner function is returned or used later,
and it keeps access to variables from its defining environment.
```

---

## Captured Environment

A captured environment is the set of outer-scope names a closure still needs.

```python
def make_prefixer(prefix: str):
    def add_prefix(value: str) -> str:
        return f"{prefix}{value}"

    return add_prefix
```

`add_prefix` captures `prefix`.

Memory model:

```text
make_prefixer("user:")
        |
        v
Function Object: add_prefix
        |
        v
Captured Environment
        |
        +-- prefix -> "user:"
```

---

## State Preservation

Closures can preserve state without using global variables.

```python
def make_counter():
    count = 0

    def counter():
        nonlocal count
        count += 1
        return count

    return counter
```

Each returned `counter` owns its own captured `count`.

---

## Factory Function

A factory function creates configured behavior.

```python
def make_multiplier(factor: int):
    def multiply(value: int) -> int:
        return value * factor

    return multiply
```

Why it matters:

- Separates configuration from business logic.
- Avoids global configuration.
- Supports FastAPI dependency factories.
- Supports Playwright configuration factories.
- Supports AI prompt builder factories.

---

## Closure vs Class

| Use Closure | Use Class |
|-------------|-----------|
| Small captured configuration | Multiple pieces of state |
| One main behavior | Many methods |
| Simple factory | Clear lifecycle needed |
| Lightweight dependency | Complex domain object |

Rule:

```text
Use a closure for small behavior with small captured state.
Use a class when the state and behavior need names, lifecycle, and structure.
```

---

## Late Binding

Closures look up captured variables when called, not when created.

Bug:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

All functions return:

```text
2
2
2
```

Fix:

```python
def f(i=i):
    return i
```

Now each function keeps its own default value.

This is also called early binding through default arguments.

---

## Common Closure Patterns

- Counter factory
- Validator factory
- Retry policy factory
- FastAPI dependency factory
- Playwright timeout or context factory
- AI prompt builder factory
- Callback factory
- Tool registration helper

---

## Common Closure Bugs

Missing `nonlocal`:

```python
def outer():
    count = 0

    def inner():
        count = count + 1
        return count

    return inner
```

This raises `UnboundLocalError` because Python treats `count` as a local name inside
`inner`.

Late binding:

```python
funcs = []

for i in range(3):
    def f():
        return i

    funcs.append(f)
```

Every function returns the final value of `i`.

Fix:

```python
for i in range(3):
    def f(i=i):
        return i

    funcs.append(f)
```

Shared mutable captured state:

```text
If a closure captures a mutable list, dictionary, messages history, page, or context,
make ownership explicit.
```

---

## Function Objects

```python
def normalize(value: str) -> str:
    return value.strip().lower()

handler = normalize
result = handler(" USER ")
```

Functions can be:

- assigned
- passed
- returned
- stored in dictionaries
- used by frameworks

---

## Callable Objects

```python
class Prefixer:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def __call__(self, value: str) -> str:
        return f"{self.prefix}{value}"
```

Use callable objects when behavior needs configuration.

---

## Decorators

Definition:

```text
Decorator = a function that receives a function and returns a function.
```

Core equivalence:

```python
@decorator
def func():
    ...
```

means:

```python
def func():
    ...


func = decorator(func)
```

Mental model:

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
function name now points to wrapper
```

---

## Wrapper Pattern

```python
def trace(func):
    def wrapper(*args, **kwargs):
        print("before")
        result = func(*args, **kwargs)
        print("after")
        return result

    return wrapper
```

The wrapper is the callable that runs after decoration.

Rules:

- Use `*args` to forward positional arguments.
- Use `**kwargs` to forward keyword arguments.
- Return the original result.
- Avoid changing the business function contract.

---

## Universal Decorator Template

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

Use this shape for most production decorators.

---

## `functools.wraps`

`functools.wraps` preserves original function metadata.

Important metadata:

- `__name__`
- `__doc__`
- `__annotations__`
- signature information used by `inspect.signature`
- framework metadata used by tools such as FastAPI

Without `wraps`, logs and debuggers may show:

```text
wrapper
```

instead of:

```text
create_user
```

Production rule:

```text
Decorator without functools.wraps is suspicious by default.
```

---

## Common Decorator Patterns

- Logging
- Timing
- Retry
- Authentication
- Authorization
- Cache
- Rate limiting
- AI token tracking
- AI request tracing
- Tool-call tracing

---

## Common Decorator Bugs

- Defining `wrapper()` without `*args` and `**kwargs`.
- Forgetting to return `func(*args, **kwargs)`.
- Forgetting `functools.wraps`.
- Logging sensitive arguments or raw prompts.
- Swallowing exceptions silently.
- Retrying non-idempotent operations.
- Wrapping async functions with sync wrappers.

---

## Iterable vs Iterator

Engineering definition:

```text
Iterable = object that can produce an iterator.
Iterator = object that produces values one by one and remembers position.
```

```python
values = [1, 2, 3]
iterator = iter(values)

print(next(iterator))  # 1
```

Why they are separated:

- Containers can be reused.
- Traversal state lives in the iterator.
- Multiple independent iterators can exist for one iterable.
- One-pass streams can still fit the same protocol.

---

## `iter()` and `next()`

`iter()` asks for an iterator.

`next()` asks an iterator for one more value.

```python
iterator = iter(["a", "b"])

print(next(iterator))  # a
print(next(iterator))  # b
```

When there are no more values, Python raises `StopIteration`.

Why not `None`?

```text
None can be real data.
StopIteration is an unambiguous end-of-stream signal.
```

---

## Generator

A generator is an iterator created by a function that uses `yield`.

```python
def numbers():
    yield 1
    yield 2
```

Calling `numbers()` creates a generator object.

The body runs when values are requested.

```text
generator function
        |
        v
generator object
        |
        v
next() -> run until yield -> pause
```

---

## `yield` vs `return`

| Keyword | Meaning |
|---------|---------|
| `return` | End the function and send back one result |
| `yield` | Produce one value, pause, and resume later |

Generator value:

```text
Not only memory saving.
The deeper value is pausable and resumable data flow.
```

---

## Generator Lifecycle

```text
Created
  |
  v
Running
  |
  v
Paused at yield
  |
  v
Running again
  |
  v
Exhausted
```

After exhaustion, the same generator does not restart.

```python
gen = (x for x in range(2))

print(list(gen))  # [0, 1]
print(list(gen))  # []
```

---

## List Comprehension vs Generator Expression

List comprehension:

```python
values = [x * 2 for x in range(3)]
```

Generator expression:

```python
values = (x * 2 for x in range(3))
```

| Use List | Use Generator |
|----------|---------------|
| Need indexing | Need streaming |
| Need length | Need one-pass processing |
| Need repeated iteration | Data is large or delayed |
| Need all results now | Need lazy evaluation |

---

## `yield from`

`yield from` delegates yielding to another iterable.

```python
def child():
    yield "a"
    yield "b"


def parent():
    yield from child()
    yield "c"
```

It is useful for composing generator pipelines.

---

## Streaming Patterns

Generator-based systems are useful for:

- FastAPI `StreamingResponse`
- LLM token streaming
- Playwright page-by-page scraping
- file processing
- log processing
- data pipelines

Pipeline vs batch:

```text
Batch:
load all -> process all -> return all

Pipeline:
load one -> process one -> return one
```

Production warnings:

- A generator can be consumed only once.
- Debugging with `list(generator)` consumes it.
- Streaming failures may happen after partial output.
- Resource cleanup must be explicit.
- Use lists when callers need reuse.

---

## Day07 Production Risk Table

| Concept | Key Point | Production Risk |
|---------|-----------|-----------------|
| Iterable | Can create iterator | Confusing shared data with traversal state |
| Iterator | Maintains traversal state | Shared iterator causes missing data |
| Generator | Pausable function and iterator | Can be consumed only once |
| `yield` | Produces value and pauses | Function body does not run at call time |
| `yield from` | Delegates iteration | Accidentally iterating strings character by character |
| `StopIteration` | End signal | Misunderstanding it as a crash |
| Generator Expression | Lazy evaluation | Debugging or aggregation can consume it |
| `list(generator)` | Converts by consuming | Later streaming sends nothing |
| `sum(generator)` | Aggregates by consuming | Second aggregation may return `0` |
| StreamingResponse | Sends chunks incrementally | Generator failure can happen after partial response |

Engineering principle:

```text
Data can be shared.
State should not be shared.
```

FastAPI:

- Request state should be request-scoped.
- Database sessions should not be casually shared across requests.

Playwright:

- Each job should use an isolated `BrowserContext`.
- Cookies, login state, and `LocalStorage` should not leak between workers.

AI Backend:

- Each LLM stream should own its token stream state.
- Do not pass the same generator to multiple consumers.

---

## Exception Handling

Engineering definition:

```text
Exception handling = how a backend detects, routes, translates, and explains failure.
```

Basic shape:

```python
try:
    result = risky_operation()
except SpecificError:
    result = recover()
```

Use `try / except` for known failure paths.

Do not use it to hide unexpected bugs.

---

## Specific Exception vs `except Exception`

Prefer:

```python
try:
    result = 10 / value
except ZeroDivisionError:
    result = 0
```

Avoid broad catching inside business logic:

```python
try:
    result = do_work()
except Exception:
    result = None
```

Rule:

```text
Catch the exception you know how to handle.
Let unknown failures propagate.
```

---

## Exception Control Flow

When an exception happens in a `try` block, later lines in that block do not run.

```python
try:
    print("A")
    print(10 / 0)
    print("B")
except ZeroDivisionError:
    print("C")

print("D")
```

Output:

```text
A
C
D
```

---

## Exception Propagation

If a function does not catch an exception, it moves up the call stack.

```text
low_level()
    |
    v
service()
    |
    v
api_handler()
    |
    v
framework boundary
```

Use propagation when a higher layer has better context for logging, retry, or response
translation.

---

## `raise`

Use `raise` when normal execution cannot continue safely.

```python
def check_age(age: int) -> None:
    if age < 0:
        raise ValueError("age must not be negative")
```

Return `None` for expected absence.

Raise for invalid operation, failed dependency, or broken invariant.

---

## Custom Exceptions

Custom exceptions encode domain meaning.

```python
class InvalidPromptError(ValueError):
    pass


class LLMRequestError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass
```

Why:

- API layer can map errors to status codes.
- Workers can decide retry vs fail.
- AI agents can record tool failure state.
- Logs become searchable by error type.

---

## Exception Chaining

Use `raise ... from ...` to preserve root cause.

```python
try:
    call_provider()
except TimeoutError as error:
    raise LLMRequestError("LLM request timed out") from error
```

Meaning:

```text
TimeoutError was the root cause.
LLMRequestError is the domain-level error.
```

---

## Traceback and Root Cause

A traceback answers:

- Which function failed?
- Which line failed?
- What exception type occurred?
- What was the root cause?
- Was the error translated correctly?

Production rule:

```text
Logs should preserve root cause without leaking sensitive data.
```

---

## Framework Error Patterns

| Context | Pattern | Risk |
|---------|---------|------|
| FastAPI | Raise `HTTPException` at API boundary | Leaking internal traceback to users |
| Service layer | Raise domain exception | Coupling business logic to HTTP |
| Playwright | Capture screenshot, cleanup, re-raise | Swallowing automation failures |
| AI Backend | Use `InvalidPromptError`, `LLMRequestError`, `ToolExecutionError`, `RateLimitError` | Collapsing all failures into `None` |

FastAPI:

- Convert validation/domain errors into HTTP responses.
- Avoid raw internal errors in user-facing responses.

Playwright:

- Separate recoverable timeout from non-recoverable login failure.
- Capture evidence before cleanup.
- Use framework-specific exception classes when needed, such as `PlaywrightTimeoutError`
  instead of bare `TimeoutError`.

AI Backend:

- Prompt validation should raise clear errors.
- LLM failures should preserve provider root cause.
- Tool failures should update agent state explicitly.

---

## Module

A module is a Python file loaded as a module object.

```text
user_service.py
        |
        v
module object
        |
        v
module namespace
```

Key point:

- A module is not copy-pasted into the importing file.
- Python executes the module and creates a runtime module object.
- The module object has its own namespace.

---

## Package

A package groups related modules and subpackages.

```text
app/
  api/
  services/
  repositories/
  schemas/
```

Production purpose:

- Organize code by responsibility.
- Create clear import boundaries.
- Make backend projects easier to review and test.

---

## Import System

Import execution flow:

```text
import module
    |
    v
check sys.modules
    |
    +-- cached -> reuse module object
    |
    +-- not cached
            |
            v
        create module object
            |
            v
        cache in sys.modules
            |
            v
        execute top-level code
            |
            v
        bind imported name
```

Important:

- Import executes top-level code.
- Import does not copy source code.
- Later imports usually reuse the cached module object.

---

## Module Cache: `sys.modules`

`sys.modules` maps module names to loaded module objects.

```python
import sys
import json

print(sys.modules["json"] is json)
```

Output:

```text
True
```

Production risk:

- Module-level mutable state is shared by every importer.
- Do not store request-specific, job-specific, or conversation-specific state in module globals.

---

## `__init__.py`

`__init__.py` marks a directory as a regular package and can define package-level exports.

```text
app/
  __init__.py
  services/
    __init__.py
```

Best practice:

- Keep `__init__.py` lightweight.
- Avoid database connections, browser launches, API calls, and hidden state mutation.
- Re-export only intentional public names.

---

## Namespace Package

Python 3.3+ supports namespace packages without `__init__.py`.

Use case:

- Split one logical package across multiple directories or distributions.

Engineering rule:

- For normal backend application code, explicit `__init__.py` is usually clearer.
- Use namespace packages only when there is a real packaging reason.

---

## Import Styles

| Style | Meaning | Use Case | Risk |
|-------|---------|----------|------|
| `import module` | Bind module name | Keep namespace visible | Can be verbose |
| `from module import name` | Bind imported object directly | Clear specific dependency | Source namespace less visible |
| `from module import *` | Import many public names | Rare package export cases | Namespace pollution |

Production guidance:

- Prefer explicit imports.
- Avoid wildcard imports.
- Choose the style that makes ownership obvious.

---

## Namespace Pollution

Namespace pollution happens when too many names enter the current namespace without clear
ownership.

Bad:

```python
from app.services.user_service import *
```

Risks:

- Name collisions
- Accidental shadowing
- Hidden dependencies
- Poor code review readability
- Harder static analysis

---

## Absolute Import vs Relative Import

Absolute import:

```python
from app.services.user_service import create_user
```

Relative import:

```python
from .user_service import create_user
```

Production rule:

- Prefer absolute imports in large backend systems.
- Use simple relative imports only when local package clarity improves.
- Avoid deep relative imports such as `from ...services import x`.

---

## Import Side Effects

An import side effect is meaningful work that happens because a module is imported.

Bad examples:

- Connect to a database at import time.
- Launch a Playwright browser at import time.
- Open a page at import time.
- Call an LLM provider at import time.
- Register request-specific or user-specific state at import time.

Better:

- Define factories at import time.
- Execute runtime work inside request handlers, workers, jobs, or explicit startup hooks.

```python
def create_client() -> LLMClient:
    return LLMClient()
```

---

## Python Import Best Practices

- Keep imports explicit.
- Keep import-time behavior lightweight.
- Keep `__init__.py` simple.
- Avoid `from module import *`.
- Prefer absolute imports for large projects.
- Avoid module-level mutable request state.
- Use factories for database sessions, browser pages, and LLM clients.
- Treat circular imports as architecture boundary warnings.

---

## Enterprise Rules

- Avoid hidden shared mutable state.
- Make mutation obvious.
- Use type hints.
- Use logging instead of `print()` in production.
- Keep functions small and readable.
- Prefer dependency injection over globals.
- Write tests for important behavior.

---

## Interview Phrases

- "Variables in Python are names bound to object references."
- "`==` compares values, while `is` compares identity."
- "Functions are first-class objects in Python."
- "Mutable defaults can leak state across calls."
- "Assignment copies references, not necessarily objects."
- "A shallow copy copies the outer container, but nested objects may still be shared."
- "A deep copy recursively copies the object tree."
- "Dictionary keys must be hashable because their hash must remain stable."
- "Python uses call by sharing for function arguments."
- "Mutation changes the object; rebinding changes the local name."
- "Rebinding a parameter does not rebind the caller's variable."
- "Python uses lexical scope, not dynamic scope."
- "LEGB means Local, Enclosing, Global, Built-in."
- "A closure is a function object plus a captured environment."
- "A captured environment preserves the outer variables needed by the returned function."
- "Closures preserve state without requiring global variables."
- "Factory functions separate configuration from business logic."
- "Use closures for small captured configuration and classes for complex state."
- "Late binding means a closure looks up a variable when the function is called."
- "The `i=i` pattern fixes late binding by storing the current value as a default argument."
- "A decorator is a function that receives a function and returns a function."
- "`@decorator` is equivalent to `func = decorator(func)`."
- "The wrapper is the callable that actually runs after decoration."
- "Production decorators usually forward `*args` and `**kwargs`."
- "`functools.wraps` preserves function metadata for debugging and frameworks."
- "Decorators are useful for cross-cutting concerns like logging, timing, retry, auth, cache, and tracing."
- "An iterable can produce an iterator; an iterator produces values one by one."
- "`StopIteration` separates end-of-stream control flow from real data values like `None`."
- "A generator is a pausable and resumable iterator created with `yield`."
- "Generators are one-pass streams and can be consumed only once."
- "Lazy evaluation improves streaming and time-to-first-result, not only memory usage."
- "`yield from` delegates yielding to another iterable."
- "Use generators for streaming patterns such as FastAPI StreamingResponse, Playwright pipelines, and AI token streaming."
- "Exception handling is production control flow, not just crash prevention."
- "Catch specific exceptions when you know how to handle them."
- "Exception propagation lets framework boundaries translate failures consistently."
- "Use `raise` when normal execution cannot continue safely."
- "Custom exceptions encode domain meaning in large backend systems."
- "`raise ... from ...` preserves root cause while translating errors."
- "FastAPI uses exceptions to turn backend failures into HTTP responses."
- "AI backend errors should distinguish prompt validation, LLM request failure, tool failure, and rate limits."
- "A module is a runtime object with its own namespace."
- "Import executes top-level code and caches the module in `sys.modules`."
- "`sys.modules` preserves module identity and prevents repeated execution."
- "Packages are architecture boundaries, not just folders."
- "I keep import-time behavior lightweight to avoid hidden startup side effects."
- "Absolute imports are often clearer in large backend systems."
- "Wildcard imports create namespace pollution and make ownership unclear."
- "Import side effects can break FastAPI startup, Playwright workers, and AI backend tests."
- "In production code, I prefer explicit dependencies and clear ownership of state."
