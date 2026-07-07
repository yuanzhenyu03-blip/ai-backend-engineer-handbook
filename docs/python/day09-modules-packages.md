# Lesson 9 — Modules & Packages

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day08 — Exception Handling

Next Lesson: Day10 — Type Hints

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain what a Python module is.
* Explain what a package is and why packages exist.
* Explain what really happens when Python executes `import`.
* Explain why modules are cached in `sys.modules`.
* Explain the difference between `import module` and `from module import name`.
* Explain why `from module import *` is dangerous in production code.
* Explain `__init__.py` and namespace packages.
* Choose between absolute and relative imports in backend projects.
* Identify import side effects and explain why they are risky.
* Connect module boundaries to FastAPI, Playwright, and AI backend architecture.

---

# Why This Matters

Day09 is not about memorizing import syntax.

It is about learning how a real Python backend is divided into files, modules, packages,
and boundaries.

Tech Lead Question:

When you write this line, what is Python really doing?

```python
import app.services.user_service
```

Think first.

Common wrong answer:

Python copies the code from `user_service.py` into the current file.

Expected student answer:

Python finds the module, creates a module object, executes the module's top-level code,
caches the module in `sys.modules`, and binds a name in the current namespace.

Tech Lead explanation:

That answer is the foundation of production Python architecture.

If import simply copied code, module design would be a formatting choice.

But import executes code.

That means module design controls:

* when database connections are created
* when environment variables are read
* when Playwright browsers are launched
* when AI tools are registered
* when prompt templates are loaded
* when side effects happen
* whether a backend starts cleanly or fails during import

This is why Day09 matters for AI backend engineering.

FastAPI apps are package systems.

Playwright automation projects are package systems.

AI agent backends are package systems.

When a repository grows, the difference between a clean module boundary and a messy import
graph becomes the difference between a maintainable system and a painful one.

```text
small script
    |
    v
many files
    |
    v
packages
    |
    v
import boundaries
    |
    v
production architecture
```

Today's lesson teaches that `import` is not a small syntax feature.

It is a runtime behavior and an architecture tool.

---

# Roadmap Position

Day09 follows Day08 naturally.

In Day08, we learned how failures travel through the call stack and how production systems
organize errors.

Today we learn where that code should live.

```text
Day08: Exception Handling
        |
        v
Day09: Modules & Packages
        |
        v
Day10: Type Hints
        |
        v
FastAPI project structure
        |
        v
Playwright worker architecture
        |
        v
AI backend package design
```

Before Day09, Python knowledge mostly lived inside one file.

After Day09, we start thinking like backend engineers:

```text
app/
  api/
  services/
  repositories/
  models/
  schemas/
  dependencies/
  errors.py
```

The question changes from:

```text
Can I write this code?
```

to:

```text
Where should this code live?
What should import what?
What side effects happen at import time?
Can another engineer understand the module boundary?
```

This is the bridge from Python foundations to real backend project structure.

---

# Lesson Map

```text
Today's Lesson

1. Why Modules Matter
2. Module Mental Model
3. Import Execution Flow
4. Module Cache: sys.modules
5. Module vs Package
6. __init__.py
7. Namespace Package
8. Namespace and Import Styles
9. Absolute vs Relative Import
10. Import Side Effects
11. FastAPI Connections
12. Playwright Connections
13. AI Backend Architecture
14. Interview Review
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

## Concept 1: Module

A module is a Python file loaded as a module object.

Example:

```text
user_service.py
```

When imported, it becomes:

```text
module object: user_service
        |
        v
module namespace:
  create_user
  get_user
  UserService
  DEFAULT_LIMIT
```

Tech Lead Question:

Is a module just a file?

Think first.

Common wrong answer:

Yes. A module is just a `.py` file.

Expected student answer:

The source file is the storage format. At runtime, Python creates a module object and gives
it a namespace.

Tech Lead explanation:

This is the same thinking we used on Day01.

Python does not only have text files.

Python has runtime objects.

```text
user_service.py
        |
        v
Python executes file
        |
        v
module object
        |
        v
namespace dictionary
```

That namespace is why we can write:

```python
import math

print(math.sqrt(16))
```

`math` is a module object.

`sqrt` is a name inside the module namespace.

## Concept 2: Import Is Execution

Import is not copy-paste.

Import is module loading and execution.

Example:

```python
# config.py
print("loading config")

API_TIMEOUT = 30
```

```python
# main.py
import config

print(config.API_TIMEOUT)
```

Output:

```text
loading config
30
```

Tech Lead Question:

Why did `loading config` print?

Expected student answer:

Because Python executed the top-level code in `config.py` during import.

Tech Lead explanation:

Top-level code runs at import time.

That is useful for defining constants, functions, and classes.

It is dangerous when the top level performs production side effects.

Bad import-time side effects:

```python
# browser.py
from playwright.sync_api import sync_playwright

playwright = sync_playwright().start()
browser = playwright.chromium.launch()
```

This is risky because merely importing `browser.py` starts infrastructure.

Better:

```python
# browser.py
from playwright.async_api import Browser, async_playwright


async def create_browser() -> Browser:
    playwright = await async_playwright().start()
    return await playwright.chromium.launch()
```

Now importing the module defines a factory.

Calling the factory performs the side effect intentionally.

## Concept 3: Import Execution Flow

Python import follows a clear flow.

```text
import app.services.user_service
        |
        v
Check sys.modules
        |
        +-- already loaded?
        |       |
        |       v
        |   reuse cached module object
        |
        +-- not loaded?
                |
                v
        find module/package
                |
                v
        create module object
                |
                v
        put module in sys.modules
                |
                v
        execute top-level code
                |
                v
        bind name in current namespace
```

Important detail:

Python stores the module in `sys.modules` before finishing execution.

That detail helps with some circular import cases, but circular imports can still produce
partially initialized modules.

Classroom Discussion:

Student:

"So import means Python runs the file once?"

Tech Lead:

"Correct, but say it more precisely. Python executes the module top-level code, creates a
module object, and caches that object. After that, later imports reuse the cached object."

This precision matters in interviews.

## Concept 4: Module Cache: `sys.modules`

`sys.modules` is a dictionary that maps module names to loaded module objects.

```python
import sys
import math

print("math" in sys.modules)
print(sys.modules["math"] is math)
```

Expected output:

```text
True
True
```

Memory model:

```text
sys.modules
    |
    v
{
  "math": <module object math>,
  "app.services.user_service": <module object user_service>
}
```

Tech Lead Question:

Why does Python cache modules?

Think first.

Common wrong answer:

Only for performance.

Expected student answer:

Performance is one reason, but caching also preserves module identity and prevents
top-level code from running repeatedly.

Tech Lead explanation:

Imagine this module:

```python
# registry.py
TOOLS = []

print("registering tools")
TOOLS.append("search")
```

If every import executed it again, `TOOLS` could be registered multiple times.

Module caching gives a stable shared module object:

```text
first import
    |
    v
execute module -> cache module

second import
    |
    v
reuse cached module -> do not execute again
```

This is helpful.

It is also a source of hidden shared state.

If a module-level list is mutated, every importer sees the same list.

```python
# state.py
messages: list[str] = []
```

```python
# handler_a.py
import state

state.messages.append("user A")
```

```python
# handler_b.py
import state

print(state.messages)
```

This can become user data leakage in an AI backend.

## Concept 5: Module vs Package

A module is usually one `.py` file.

A package is a directory that groups modules and subpackages.

```text
app/
  services/
    user_service.py
    email_service.py
```

Here:

```text
user_service.py  -> module
email_service.py -> module
services/        -> package
app/             -> package
```

Tech Lead Question:

Why do packages exist?

Expected student answer:

To organize related modules and create clear namespaces.

Tech Lead explanation:

Packages are not just folders.

They are architecture boundaries.

```text
app.api        -> HTTP boundary
app.services   -> business logic
app.repositories -> data access
app.schemas    -> request/response models
app.agents     -> AI agent orchestration
```

Good package design tells future engineers where code belongs.

Bad package design turns a repository into a pile of unrelated files.

## Concept 6: `__init__.py`

Traditionally, a directory becomes a regular Python package when it contains
`__init__.py`.

```text
app/
  __init__.py
  services/
    __init__.py
    user_service.py
```

`__init__.py` can:

* mark a directory as a package
* initialize package-level names
* re-export selected objects
* document package intent

Example:

```python
# app/services/__init__.py
from app.services.user_service import create_user

__all__ = ["create_user"]
```

Then:

```python
from app.services import create_user
```

Tech Lead warning:

Keep `__init__.py` lightweight.

Do not connect to databases, start browsers, call LLM providers, or register hidden global
state inside `__init__.py`.

Why?

Because importing a package executes `__init__.py`.

```text
import app.services
        |
        v
execute app/__init__.py
        |
        v
execute app/services/__init__.py
```

If `__init__.py` has heavy side effects, any import can accidentally start half the
application.

## Concept 7: Namespace Package

Since Python 3.3, a package can exist without `__init__.py`.

This is called a namespace package.

```text
plugins_a/
  ai_tools/
    search.py

plugins_b/
  ai_tools/
    browser.py
```

Python can combine multiple directories into one logical package namespace:

```text
ai_tools
  search
  browser
```

Why does this exist?

Namespace packages support large systems where one package namespace may be split across
multiple distributions.

For normal application code, explicit `__init__.py` is often clearer.

Tech Lead guidance:

In an AI backend training project, prefer explicit package boundaries unless there is a
clear reason to use namespace packages.

Clarity wins.

## Concept 8: Namespace

A namespace maps names to objects.

Module namespace:

```python
# user_service.py
DEFAULT_LIMIT = 100


def create_user(name: str) -> dict[str, str]:
    return {"name": name}
```

Runtime:

```text
user_service module namespace
    |
    v
{
  "DEFAULT_LIMIT": 100,
  "create_user": <function object>
}
```

Day01 connection:

Functions are objects.

Modules store names that reference objects.

Day09 is Day01 at project scale.

## Concept 9: `import module` vs `from module import name`

Style 1:

```python
import app.services.user_service

app.services.user_service.create_user("Alice")
```

Style 2:

```python
from app.services.user_service import create_user

create_user("Alice")
```

Both import the module.

The difference is what name is bound in the current namespace.

```text
import module
        |
        v
current namespace gets module name

from module import name
        |
        v
current namespace gets imported object name
```

Tech Lead Question:

Which style is more readable?

Expected student answer:

It depends. `import module` keeps the source namespace visible. `from module import name`
is concise when the imported name is clear.

Engineering rule:

Use the style that makes ownership obvious.

Good:

```python
from app.services.user_service import create_user
from app.errors import InvalidPromptError
```

Also good when namespace matters:

```python
import logging
import pathlib

logger = logging.getLogger(__name__)
path = pathlib.Path("data")
```

## Concept 10: Why `from module import *` Is Dangerous

Avoid this in production code:

```python
from app.services.user_service import *
```

Why?

Because it pollutes the current namespace.

```text
before import *
    |
    v
current namespace:
  create_user?
  delete_user?
  DEFAULT_LIMIT?
  helper?

after import *
    |
    v
many names appear without clear ownership
```

Common production problems:

* name collisions
* unclear ownership
* poor code review readability
* harder static analysis
* accidental shadowing
* hidden dependencies

Tech Lead Review:

If a pull request uses `from x import *`, I would ask:

* Which names are actually needed?
* Could this shadow an existing name?
* Will a teammate know where this function came from?
* Can the linter and IDE track this reliably?

Most production teams reject wildcard imports except in very narrow package-export cases.

## Concept 11: Absolute Import vs Relative Import

Absolute import:

```python
from app.services.user_service import create_user
```

Relative import:

```python
from .user_service import create_user
from ..errors import InvalidPromptError
```

Tech Lead Question:

Which one should we prefer in a large backend system?

Expected student answer:

Absolute imports are usually preferred because they show the full package path and are
easier to understand during code review.

Tech Lead explanation:

Absolute imports are explicit.

```text
from app.services.user_service import create_user
     |
     v
source package is obvious
```

Relative imports can be acceptable inside a small package, but deeply nested relative
imports become hard to read.

```python
from ...services.users.factory import create_user_service
```

This forces the reader to count dots.

Production guidance:

* Prefer absolute imports for application code.
* Use simple relative imports only when they improve local package clarity.
* Avoid deep relative import chains.
* Avoid import paths that create circular dependencies.

## Concept 12: Import Side Effects

An import side effect is any meaningful action that happens just because a module is
imported.

Examples:

```python
# bad: db.py
engine = create_engine(DATABASE_URL)
session = Session(engine)
```

```python
# bad: crawler.py
browser = launch_browser()
page = browser.new_page()
```

```python
# bad: agent.py
response = llm_client.chat("warm up")
```

These modules do work during import.

That creates production risks:

* application startup becomes fragile
* tests become slow or flaky
* imports fail when environment variables are missing
* workers start resources too early
* circular imports become harder to debug
* AI tools register or execute before configuration is ready

Better pattern:

```python
def create_session() -> Session:
    return Session(engine)
```

```python
async def create_page(context: BrowserContext) -> Page:
    return await context.new_page()
```

```python
def build_prompt(system_message: str) -> PromptBuilder:
    return PromptBuilder(system_message=system_message)
```

Import should define tools.

Runtime should execute tools.

```text
Import time:
  define classes
  define functions
  define constants

Runtime:
  connect to database
  launch browser
  call LLM
  register request state
```

## Concept 13: Circular Imports

Circular imports happen when modules import each other.

```text
user_service.py imports email_service.py
email_service.py imports user_service.py
```

Risk:

One module may be partially initialized when another module tries to access it.

Symptoms:

* `ImportError`
* `AttributeError`
* "partially initialized module"
* code that works in one entry point but fails in another

Tech Lead guidance:

Circular imports usually indicate a boundary problem.

Common fixes:

* move shared types or constants to a lower-level module
* invert dependencies
* use dependency injection
* move import inside a function only as a tactical workaround
* split service responsibilities more clearly

Do not solve circular imports by randomly moving imports until the error disappears.

Solve the architecture boundary.

---

# Engineering Thinking

## Import Is an Architecture Boundary

A junior engineer asks:

"Where should I put this function?"

A tech lead asks:

"Who should be allowed to import this function?"

That is the engineering shift.

Module boundaries decide which parts of the system know about which other parts.

Good boundary:

```text
api layer -> service layer -> repository layer
```

Risky boundary:

```text
repository layer -> api layer
service layer -> route module
tool module -> global app object
```

When lower-level code imports higher-level code, the system becomes harder to test and
harder to reuse.

## Engineering Principle: Import Should Be Boring

Import should usually be boring.

That means importing a module should not:

* connect to production services
* mutate global request state
* start a Playwright browser
* execute an LLM call
* read user-specific session data
* run a background task

Tech Lead Question:

Why should import be boring?

Expected student answer:

Because import can happen during app startup, testing, worker boot, CLI commands, or
interactive debugging. If import has side effects, every environment becomes risky.

Tech Lead explanation:

Production systems need predictable startup.

If imports do real work, startup becomes hidden runtime behavior.

That makes failures hard to locate.

```text
pytest imports module
        |
        v
module connects to real database
        |
        v
test fails before test starts
```

This is not a testing problem.

It is an import side effect problem.

## Tech Lead Review Checklist

When reviewing module and package design, a tech lead checks:

* Are imports explicit?
* Are package boundaries clear?
* Are there wildcard imports?
* Does import time perform runtime work?
* Are there circular dependencies?
* Is `__init__.py` lightweight?
* Are absolute imports used where they improve clarity?
* Does each module have one responsibility?
* Could this module be tested without booting the whole app?

## CTO Thinking

A CTO does not care whether a repository has many files.

A CTO cares whether the package design supports growth.

Questions a CTO would ask:

* Can new engineers find code quickly?
* Can teams work on different packages without constant conflicts?
* Can the API layer change without rewriting tools?
* Can Playwright automation be scaled into workers?
* Can AI tools be registered safely?
* Can the system start predictably in production?
* Can tests import modules without external side effects?

If package boundaries are weak, every future feature becomes slower.

Day09 is where Python syntax becomes engineering architecture.

## AI Backend Package Boundaries

AI backend projects fail quickly when module boundaries are unclear.

Bad shape:

```text
app.py
  routes
  prompts
  tools
  provider calls
  session state
  retry logic
  error handling
```

This works for a demo.

It does not scale into a maintainable backend.

Better shape:

```text
app/
  agents/
    customer_support_agent.py
  prompts/
    support_prompt.py
  tools/
    search_tool.py
    browser_tool.py
  llm/
    client.py
    provider_errors.py
  sessions/
    conversation_store.py
  errors.py
```

Tech Lead Question:

Why not register and execute every tool at import time?

Think first.

Expected student answer:

Because import can happen during startup, tests, or worker boot. Tool registration may be
intentional, but tool execution, provider calls, and user-specific state must happen at
runtime.

Tech Lead explanation:

AI backend imports should define capabilities.

Requests and jobs should execute capabilities.

```text
import time
    |
    v
define prompt builders
define tool functions
define LLM client factories

runtime
    |
    v
build request state
call provider
execute tools
stream tokens
```

This separation prevents prompt pollution, hidden provider calls, shared conversation
state, and unpredictable tests.

---

# Classroom Exercises

## Exercise 1: Is Import Copying Code?

Question:

What happens when Python runs this?

```python
import config
```

Think first.

Common wrong answer:

Python copies `config.py` into the current file.

Expected Answer:

Python finds `config.py`, creates a module object, executes its top-level code, stores the
module in `sys.modules`, and binds `config` in the current namespace.

Explanation:

Import is execution plus caching, not copy-paste.

Follow-up Question:

Why does this matter for database connections and Playwright browsers?

## Exercise 2: Output Prediction

Starter Code:

```python
# settings.py
print("loading settings")

TIMEOUT = 30
```

```python
# main.py
import settings
import settings

print(settings.TIMEOUT)
```

Think first.

Expected Output:

```text
loading settings
30
```

Explanation:

The first import executes `settings.py`.

The second import reuses the cached module from `sys.modules`.

## Exercise 3: `sys.modules`

Starter Code:

```python
import sys
import json

print("json" in sys.modules)
print(sys.modules["json"] is json)
```

Think first.

Expected Output:

```text
True
True
```

Explanation:

`sys.modules["json"]` points to the same module object bound to the name `json`.

Tech Lead follow-up:

If module objects are cached, what risk exists with module-level mutable state?

Expected student answer:

Every importer shares the same module object and the same module-level mutable objects.

## Exercise 4: Module vs Package

Question:

In this structure, identify modules and packages:

```text
app/
  __init__.py
  api/
    __init__.py
    users.py
  services/
    __init__.py
    user_service.py
```

Expected Answer:

Packages:

* `app`
* `app.api`
* `app.services`

Modules:

* `app.api.users`
* `app.services.user_service`

Explanation:

Directories with `__init__.py` are regular packages. `.py` files are modules.

## Exercise 5: `__init__.py` Execution

Starter Code:

```python
# app/__init__.py
print("loading app")
```

```python
# app/services/__init__.py
print("loading services")
```

```python
# app/services/user_service.py
print("loading user_service")
```

```python
import app.services.user_service
```

Expected Output:

```text
loading app
loading services
loading user_service
```

Explanation:

Python initializes parent packages before importing the submodule.

Tech Lead follow-up:

Why should `__init__.py` stay lightweight?

Expected student answer:

Because importing a package executes `__init__.py`. Heavy logic there can create hidden
startup side effects.

## Exercise 6: Namespace Pollution

Starter Code:

```python
from email_service import *

send("hello")
```

Question:

Why is this risky in production?

Expected Answer:

It hides where `send` came from, can create name collisions, and makes code review harder.

Explanation:

Production code should make dependencies explicit.

Better:

```python
from email_service import send_email

send_email("hello")
```

## Exercise 7: Absolute vs Relative Import

Question:

Which import is easier to review in a large FastAPI project?

```python
from app.services.user_service import create_user
```

or:

```python
from ...services.user_service import create_user
```

Expected Answer:

The absolute import is usually easier to review because it shows the full project path.

Explanation:

Relative imports can be useful locally, but deep relative imports force the reader to
reconstruct the package position.

## Exercise 8: Import Side Effect Review

Starter Code:

```python
# llm_client.py
from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model="example-model",
    input="warm up",
)
```

Question:

What would a tech lead reject here?

Expected Answer:

The module calls the LLM provider at import time.

Explanation:

Importing `llm_client.py` should define reusable client factories or functions. Runtime
code should decide when to call the provider.

Better:

```python
from openai import OpenAI


def create_client() -> OpenAI:
    return OpenAI()
```

## Exercise 9: FastAPI Package Design

Question:

Where should route handlers, service logic, request schemas, and domain exceptions live?

Expected Answer:

One reasonable structure:

```text
app/
  api/
    routes/
  services/
  schemas/
  errors.py
  dependencies.py
```

Explanation:

The API layer owns HTTP details. The service layer owns business logic. Schemas define
request and response shapes. Errors define domain failures.

## Exercise 10: AI Backend Module Boundary

Question:

Design package boundaries for an AI backend with prompts, tools, LLM provider clients,
and conversation state.

Expected Answer:

One reasonable structure:

```text
app/
  agents/
  prompts/
  tools/
  llm/
  sessions/
  errors.py
```

Explanation:

Prompt building, tool execution, provider calls, and session state have different
responsibilities. Putting everything in one module makes testing and failure handling
harder.

---

# FastAPI Connections

FastAPI projects are package systems.

A production-style FastAPI application often looks like this:

```text
app/
  main.py
  api/
    routes/
      users.py
      auth.py
  services/
    user_service.py
    auth_service.py
  repositories/
    user_repository.py
  schemas/
    user.py
  dependencies.py
  errors.py
  core/
    config.py
```

## Import Boundaries in FastAPI

Good direction:

```text
api routes
    |
    v
services
    |
    v
repositories
```

Risky direction:

```text
repositories
    |
    v
api routes
```

Repository code should not know about HTTP routes.

Service code should not depend on a specific router module.

FastAPI route modules can import services because routes are the boundary where HTTP
requests enter the system.

## `Depends()` and Imports

FastAPI dependencies are often imported into route modules:

```python
from fastapi import Depends, APIRouter

from app.dependencies import get_current_user
from app.services.user_service import create_user

router = APIRouter()
```

This is fine because import time defines dependencies and routes.

But this is dangerous:

```python
# dependencies.py
current_user = load_user_from_request()
```

There is no request at import time.

Request state belongs to request lifecycle, not module import.

## Import Side Effects in FastAPI

Bad:

```python
# db.py
session = create_session()
```

Better:

```python
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

Tech Lead explanation:

The module can define `get_session`.

The request lifecycle should create and close the session.

Day09 connects back to Day07:

```text
module defines generator dependency
request consumes dependency
state is isolated per request
```

## FastAPI Production Rule

Keep import-time behavior lightweight:

* define routers
* define schemas
* define dependency factories
* define exception types
* avoid request-specific state
* avoid database session creation at import time
* avoid calling external providers during import

---

# Playwright Connections

Playwright automation projects also need clean module boundaries.

Example structure:

```text
automation/
  browser_factory.py
  contexts.py
  pages/
    login_page.py
    dashboard_page.py
  jobs/
    scrape_orders.py
  storage/
    cookies.py
  errors.py
```

## Browser, Context, and Page Should Not Be Global Imports

Bad:

```python
# page.py
page = browser.new_page()
```

Why bad?

Importing the module creates a page.

That page may be shared across jobs, tests, or workers.

Better:

```python
from playwright.async_api import BrowserContext, Page


async def create_page(context: BrowserContext) -> Page:
    return await context.new_page()
```

Now the caller controls lifecycle.

```text
worker job
    |
    v
create context
    |
    v
create page
    |
    v
run job
    |
    v
close context
```

## Import Side Effects in Automation

Common Playwright import side effects:

* launching browser during import
* opening a page during import
* loading cookies into a global object
* mutating shared headers
* starting background jobs from a module top level

Production risk:

Two jobs can accidentally share login state, cookies, local storage, or page state.

Day09 connection:

```text
module boundary controls lifecycle ownership
```

If a module creates a page at import time, the module owns the page.

If a factory creates a page during a job, the job owns the page.

That difference matters.

---

# English Interview

## Key Vocabulary

* module
* package
* namespace
* import system
* module object
* module cache
* `sys.modules`
* import side effect
* absolute import
* relative import
* namespace package
* namespace pollution
* circular import

## Beginner Questions

Question:

What is a Python module?

Standard Answer:

A Python module is a file that Python loads as a module object. The module object has its
own namespace containing functions, classes, constants, and other names defined by the
module.

Interview expression:

"A module is not just a text file. At runtime, Python creates a module object and stores
the module's names in its namespace."

Question:

What is a Python package?

Standard Answer:

A package is a directory that groups related modules and subpackages under a common
namespace.

Interview expression:

"Packages help organize a codebase into clear boundaries, such as API, services,
repositories, and schemas in a FastAPI project."

Question:

What does `__init__.py` do?

Standard Answer:

`__init__.py` marks a directory as a regular package and can initialize package-level names
or re-export selected objects.

Interview expression:

"I keep `__init__.py` lightweight because it runs when the package is imported."

## Intermediate Questions

Question:

Explain Python import execution.

Standard Answer:

Python checks `sys.modules`, finds the module if it is not already loaded, creates a module
object, stores it in the module cache, executes the module's top-level code, and binds the
requested name in the current namespace.

Follow-up Question:

Why does top-level code run during import?

Question:

Why is a module executed only once?

Standard Answer:

After the first import, Python stores the module object in `sys.modules`. Later imports
reuse the cached module object instead of executing the module again.

Follow-up Question:

What production risk comes from shared module-level mutable state?

Question:

What is an import side effect?

Standard Answer:

An import side effect is work that happens simply because a module is imported, such as
connecting to a database, launching a browser, or calling an external API.

Engineering perspective:

Import side effects make startup, testing, and worker execution unpredictable.

## Senior Questions

Question:

Explain Python's import mechanism.

Standard Answer:

Python resolves the module path, checks the module cache in `sys.modules`, creates a module
object for unloaded modules, executes top-level code to populate the module namespace, and
binds the requested name in the importing module. The cached module object preserves module
identity and prevents repeated execution.

Engineering perspective:

Understanding import helps design clean package boundaries and avoid hidden startup side
effects.

Question:

Why are absolute imports preferred in large backend systems?

Standard Answer:

Absolute imports show the full package path, make ownership clear, improve code review,
and reduce confusion in large repositories.

Engineering perspective:

Deep relative imports force readers to reconstruct location from dots. In large systems,
clarity usually matters more than shorter import lines.

Question:

What problems can namespace pollution cause?

Standard Answer:

Namespace pollution can cause name collisions, hidden dependencies, accidental shadowing,
and poor readability. Wildcard imports make it harder to know where a name came from.

Engineering perspective:

In production code, explicit imports make ownership and dependencies reviewable.

Question:

How should packages be organized in a FastAPI project?

Standard Answer:

I would separate API routes, services, repositories, schemas, dependencies, configuration,
and domain errors into clear packages or modules. Route modules can import services, but
lower-level code should not depend on HTTP route modules.

Engineering perspective:

Package structure should reflect dependency direction and lifecycle ownership.

Question:

How do module boundaries affect AI backend architecture?

Standard Answer:

AI backends should separate prompts, tools, LLM provider clients, agent orchestration,
session state, and domain errors. Clear module boundaries prevent side effects, simplify
testing, and make failure handling easier.

Engineering perspective:

If prompt building, tool execution, provider calls, and session state are mixed in one
module, the system becomes hard to test, debug, and scale.

---

# Today's Takeaway

Python import is not copy-paste.

Python import is runtime behavior:

```text
find module
    |
    v
create module object
    |
    v
execute top-level code
    |
    v
cache in sys.modules
    |
    v
bind name
```

Modules and packages are not only file organization.

They are engineering boundaries.

Today's most important production rules:

* Keep import-time behavior lightweight.
* Avoid wildcard imports.
* Prefer explicit package boundaries.
* Prefer absolute imports in large backend projects.
* Keep `__init__.py` simple.
* Avoid shared module-level mutable request state.
* Use factories for runtime resources.
* Treat import side effects as production risks.

If Day08 taught us how failures move through a system, Day09 teaches us where code should
live so those failures can be handled cleanly.

---

# Before Next Lesson Checklist

Before Day10, confirm you can answer these without looking at the notes:

- [ ] What is a Python module?
- [ ] What is a Python package?
- [ ] What happens when Python executes `import`?
- [ ] What is `sys.modules`?
- [ ] Why is a module usually executed only once?
- [ ] What does `__init__.py` do?
- [ ] What is a namespace package?
- [ ] What is the difference between `import module` and `from module import name`?
- [ ] Why is `from module import *` risky?
- [ ] What is namespace pollution?
- [ ] What is the difference between absolute and relative imports?
- [ ] What is an import side effect?
- [ ] Why should FastAPI request state not be created at import time?
- [ ] Why should Playwright `Page` objects not be global module-level objects?
- [ ] How should an AI backend organize prompts, tools, LLM clients, and session state?
