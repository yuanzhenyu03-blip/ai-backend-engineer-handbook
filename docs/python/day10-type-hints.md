# Lesson 10 — Type Hints

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day09 — Modules & Packages

Next Lesson: Day11 — Object-Oriented Programming

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain Type Hints as interface contracts.
* Explain why Type Hints are not runtime checks by default.
* Add parameter and return type hints to backend functions.
* Use `list[T]`, `dict[K, V]`, `tuple`, `set[T]`, `User | None`, `Union`, `TypeVar`, and `Generic`.
* Explain type inference and why IDEs can provide better autocomplete.
* Explain why `T -> T` preserves information better than `object -> object`.
* Connect Type Hints to FastAPI, Pydantic, OpenAPI, Playwright, and AI backend systems.
* Identify common Type Hint mistakes in production code.
* Answer beginner, intermediate, and senior Type Hint interview questions.

---

# Why This Matters

Type Hints are not decoration.

They are engineering contracts.

Tech Lead Question:

If Python does not check Type Hints at runtime by default, why do large backend teams still
care so much about them?

Think first.

Student Answer:

"Maybe because they make code easier to read?"

Tech Lead:

That is true, but incomplete.

Type Hints matter because they tell humans, tools, frameworks, and AI assistants what a
function promises.

```text
without Type Hints
    |
    v
reader guesses shape
IDE guesses methods
framework guesses schema
AI guesses intent

with Type Hints
    |
    v
interface contract
better autocomplete
better static checking
better generated docs
better API validation
better AI-assisted coding
```

A backend engineer writes code for other engineers and future systems.

In FastAPI, Type Hints become request models, response models, dependency contracts, and
OpenAPI documentation.

In Playwright, Type Hints help us distinguish `Browser`, `BrowserContext`, `Page`,
`Locator`, and storage state.

In AI backend systems, Type Hints make message shape, tool input, tool output, agent tasks,
and generic response wrappers explicit.

Common production bug:

```python
def run_tool(payload):
    return payload["result"]
```

What is `payload`?

Is it a dictionary?

Is `result` a string?

Can it be missing?

Can it be `None`?

A Type Hint turns guessing into a contract:

```python
def run_tool(payload: dict[str, str]) -> str:
    return payload["result"]
```

That is still not runtime validation by itself.

But now the contract is visible.

This is the core of Day10:

```text
Type Hints = Interface Contract
```

---

# Roadmap Position

Day09 taught module and package boundaries.

Day10 teaches function and data contracts inside those boundaries.

```text
Day09: Where should code live?
        |
        v
Day10: What does each boundary promise?
        |
        v
Day11: Object-oriented design
        |
        v
FastAPI models and dependencies
        |
        v
AI backend tool contracts
```

Modules organize code at the file and package level.

Type Hints organize expectations at the function, class, and data level.

Together:

```text
package boundary
    |
    v
module boundary
    |
    v
function signature
    |
    v
type contract
```

This is why Day10 belongs before OOP and FastAPI.

Before building classes and API systems, we need to describe what values flow through the
system.

---

# Lesson Map

```text
Today's Lesson

1. Type Hints as Interface Contracts
2. Runtime Behavior
3. Parameter Type Hints
4. Return Type Hints
5. Collection Types
6. Optional and Union
7. Type Inference
8. TypeVar and Generic
9. FastAPI Type-Driven Design
10. Playwright Object Types
11. AI Backend Message and Tool Types
12. Interview Review
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

## Concept 1: Type Hints Are Interface Contracts

Type Hints describe what a function expects and returns.

```python
def create_user(name: str, age: int) -> dict[str, object]:
    return {"name": name, "age": age}
```

Tech Lead Question:

What does this signature promise?

Think first.

Expected student answer:

It expects `name` to be a string and `age` to be an integer. It returns a dictionary whose
keys are strings and whose values may be different object types.

Tech Lead explanation:

Exactly.

But notice the word "promise."

Python will not automatically enforce this function at runtime:

```python
create_user("Alice", "18")
```

This can still run unless the function body fails.

Type Hints are mostly for:

* human readers
* IDE autocomplete
* static type checkers
* framework introspection
* API documentation
* AI coding assistants
* long-term maintainability

Mental model:

```text
function signature
        |
        v
interface contract
        |
        +--> human understanding
        +--> static analysis
        +--> framework schema
        +--> AI assistant context
```

## Concept 2: Type Hints Are Not Runtime Checks by Default

Classroom Coding Practice:

```python
def greet(name: str) -> str:
    return "Hello, " + name


print(greet("Alice"))
print(greet(123))
```

Expected result:

The first call works.

The second call raises a runtime error because string concatenation fails, not because
Python checked the Type Hint before execution.

Tech Lead Question:

Did Python reject `123` because of the Type Hint?

Expected student answer:

No. The Type Hint did not enforce the type by itself. The function failed when the body
tried to concatenate a string and an integer.

Tech Lead explanation:

This distinction matters in interviews.

Say it clearly:

```text
Type Hints describe expected types.
They are not runtime validation by default.
Frameworks such as FastAPI and Pydantic can use them to perform validation.
```

## Concept 3: Parameter Type Hints

Parameter Type Hints describe what callers should pass.

```python
def calculate_total(price: float, quantity: int) -> float:
    return price * quantity
```

Engineering meaning:

```text
caller responsibility:
  pass price as float
  pass quantity as int

function responsibility:
  return float
```

Without hints:

```python
def calculate_total(price, quantity):
    return price * quantity
```

The caller has to guess.

In small scripts, guessing may be tolerable.

In backend systems, guessing becomes production risk.

## Concept 4: Return Type Hints

Return Type Hints tell the caller what comes back.

```python
def get_user_id(email: str) -> int:
    return 1001
```

Tech Lead Question:

Why is the return type often more important than the parameter type?

Think first.

Expected student answer:

Because callers depend on the returned value and will call methods or access fields based
on what they think it is.

Tech Lead explanation:

Exactly.

Return types prevent downstream guessing.

Bad:

```python
def find_user(email: str):
    ...
```

Does this return a user?

`None`?

A dictionary?

A tuple?

Better:

```python
def find_user(email: str) -> User | None:
    ...
```

Now the caller knows:

```text
result may be User
result may be None
caller must handle both
```

## Concept 5: Basic Types

Common basic annotations:

```python
name: str = "Alice"
age: int = 30
score: float = 98.5
is_active: bool = True
```

In production code, annotate public function boundaries first:

```python
def activate_user(user_id: int) -> bool:
    ...
```

Do not annotate every obvious local variable just to look professional.

This is enough:

```python
total = price * quantity
```

The type is obvious from context.

Tech Lead guidance:

Type Hints should reduce ambiguity.

They should not create visual noise.

## Concept 6: `list[T]`

Use `list[T]` when every item should have the same type.

```python
def normalize_tags(tags: list[str]) -> list[str]:
    return [tag.strip().lower() for tag in tags]
```

Why `list[str]` is better than `list`:

```text
list
    |
    v
container only
item type unknown

list[str]
    |
    v
container known
item type known
```

Tech Lead Question:

Why does `list[User]` help more than `list`?

Expected student answer:

Because it tells readers and tools that each item is a `User`, so item fields and methods
are known.

Production risk with plain `list`:

```python
def send_emails(users: list) -> None:
    for user in users:
        send_email(user.email)
```

The function assumes every item has `.email`, but the signature does not say that.

Better:

```python
def send_emails(users: list[User]) -> None:
    for user in users:
        send_email(user.email)
```

## Concept 7: `dict[K, V]`

Use `dict[K, V]` for key and value types.

```python
def count_statuses(statuses: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}

    for status in statuses:
        result[status] = result.get(status, 0) + 1

    return result
```

Meaning:

```text
dict[str, int]
    |
    +--> keys are str
    +--> values are int
```

Common mistake:

```python
metadata: dict = {}
```

Better when the shape is known:

```python
metadata: dict[str, str] = {}
```

If the shape is mixed and domain-specific, create a model later.

Do not hide important structure in `dict[str, object]` unless you truly need flexibility.

## Concept 8: `tuple` and `set[T]`

Tuple can describe fixed position data:

```python
def get_coordinates() -> tuple[float, float]:
    return 39.9, 116.4
```

Set describes unique items:

```python
def collect_permissions(roles: list[str]) -> set[str]:
    return set(roles)
```

Engineering guidance:

Use tuple when position has meaning.

Use set when uniqueness matters.

Do not use tuple just because it is short.

If the data has business meaning, a class or Pydantic model may be clearer later.

## Concept 9: `User | None`

`User | None` means the value may be a `User` or may be missing.

```python
def find_user(email: str) -> User | None:
    ...
```

This forces the caller to think:

```python
user = find_user("a@example.com")

if user is None:
    raise ValueError("user not found")

send_email(user.email)
```

Tech Lead Question:

Why is this better than returning `User` and secretly returning `None`?

Expected student answer:

Because the type contract makes the missing case explicit.

Tech Lead explanation:

Exactly.

Silent `None` is one of the most common backend bugs.

Type Hints make optional state visible at the boundary.

## Concept 10: `Optional` and `Union`

Modern Python:

```python
User | None
```

Older style:

```python
from typing import Optional

Optional[User]
```

They mean the same thing:

```text
Optional[User] == User | None
```

`Union` means one of multiple possible types:

```python
from typing import Union

def parse_id(raw: str) -> Union[int, str]:
    ...
```

Modern style:

```python
def parse_id(raw: str) -> int | str:
    ...
```

Tech Lead guidance:

Do not overuse `Union`.

If a function returns many unrelated types, the interface may be unclear.

Common bug:

```python
def get_value() -> str | int | None | bool:
    ...
```

This is technically valid.

It is also a warning sign.

## Concept 11: Type Inference

Type inference means tools can infer a type from context.

```python
name = "Alice"
count = 3
users = ["Alice", "Bob"]
```

A type checker can infer:

```text
name  -> str
count -> int
users -> list[str]
```

Tech Lead Question:

Should we annotate every local variable?

Expected student answer:

No. If the type is obvious, type inference is enough.

Tech Lead explanation:

Correct.

Type Hints should clarify boundaries and ambiguous values.

Good places to annotate:

* public functions
* return values
* empty collections
* complex data structures
* framework boundaries
* AI tool contracts

Usually unnecessary:

```python
name: str = "Alice"
total: int = 1 + 2
```

## Concept 12: Empty Collections Need Help

Empty collections often need explicit types.

```python
messages = []
```

What goes inside?

Strings?

Chat messages?

Tool results?

Better:

```python
messages: list[ChatMessage] = []
```

This matters in AI backend systems:

```python
conversation: list[ChatMessage] = []
tool_results: list[ToolResult] = []
```

Now the system knows what the collection is meant to hold.

## Concept 13: `TypeVar`

`TypeVar` preserves relationships between input and output types.

Bad generic-looking function:

```python
def identity(value: object) -> object:
    return value
```

Problem:

The function returns the same object, but the type contract loses that information.

```python
name = identity("Alice")
```

The checker only knows:

```text
name: object
```

Better:

```python
from typing import TypeVar

T = TypeVar("T")


def identity(value: T) -> T:
    return value
```

Now:

```text
identity("Alice") -> str
identity(123)     -> int
identity(user)    -> User
```

Tech Lead Question:

Why is `T -> T` better than `object -> object`?

Expected student answer:

Because `T` preserves the relationship between the input type and output type.

Tech Lead explanation:

Exactly.

`object` says "anything comes in and an unknown object comes out."

`T` says "whatever type comes in, the same type comes out."

That is a stronger contract.

## Concept 14: `Generic`

Generic types describe reusable containers or wrappers.

AI backend example:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Response(Generic[T]):
    data: T
    error: str | None = None
```

Usage:

```python
user_response: Response[User]
task_response: Response[AgentTask]
message_response: Response[list[ChatMessage]]
```

Why this matters:

```text
Response[T]
    |
    v
same wrapper
different payload type
payload type preserved
```

Common mistake:

```python
class Response:
    data: object
```

This loses useful information.

A generic wrapper keeps the relationship between the wrapper and the payload.

## Concept 15: Common Bugs

Bug 1: Type too broad.

```python
def handle_payload(payload: object) -> object:
    ...
```

Problem:

The contract says almost nothing.

Bug 2: Plain collection.

```python
def process(items: list) -> list:
    ...
```

Problem:

The item type is unknown.

Bug 3: Hidden `None`.

```python
def find_user(email: str) -> User:
    if not exists(email):
        return None
```

Problem:

The return type lies.

Better:

```python
def find_user(email: str) -> User | None:
    ...
```

Bug 4: Overusing `Union`.

```python
def get_result() -> str | int | dict[str, object] | None:
    ...
```

Problem:

Callers now need too many branches.

Bug 5: Generic without preserving relationship.

```python
def first(items: list[object]) -> object:
    return items[0]
```

Better:

```python
def first(items: list[T]) -> T:
    return items[0]
```

---

# Engineering Thinking

## Type Hints Are Boundary Design

A backend system is a set of boundaries.

```text
HTTP request
    |
    v
route function
    |
    v
service function
    |
    v
repository function
    |
    v
database
```

Every boundary passes values.

Type Hints explain those values.

Without Type Hints:

```text
data flows through system
        |
        v
engineers guess shape
```

With Type Hints:

```text
data flows through system
        |
        v
contracts describe shape
```

## When Should You Write Type Hints?

Write Type Hints for:

* public functions
* service functions
* repository functions
* API handlers
* dependency functions
* Playwright helper functions
* AI tool functions
* message and task models
* empty collections
* complex returns

Usually skip Type Hints for:

* obvious local variables
* throwaway script variables
* expressions where inference is clearer
* code where the annotation is less readable than the value

Tech Lead Principle:

Use Type Hints to reduce uncertainty.

Do not use Type Hints to decorate obvious code.

## Production Risks

Type Hints prevent these classes of mistakes:

* passing a `Page` where a `BrowserContext` is expected
* returning `None` from a function that claims to return `User`
* mixing user messages and tool messages in one untyped list
* passing a raw dictionary where a request model is expected
* losing payload type inside a generic response wrapper
* using `object` so broadly that tooling cannot help

Type Hints do not replace tests.

They make the contract visible before runtime.

## Code Review Thinking

A tech lead reviewing Type Hints asks:

* Does this function boundary need a type contract?
* Is the return type honest?
* Is `None` represented explicitly?
* Is a plain `list` hiding item type?
* Is `dict[str, object]` hiding a real model?
* Is `object` too broad?
* Would `TypeVar` preserve a relationship better?
* Will FastAPI or Pydantic need this annotation?
* Will AI-assisted tools understand this function contract?

## CTO Thinking

A CTO cares about speed of change.

Type Hints help because:

* new engineers understand interfaces faster
* IDEs catch more mistakes before review
* refactors are safer
* FastAPI documentation stays accurate
* AI coding assistants receive better context
* production debugging has clearer contracts

Type Hints are not bureaucracy.

They are maintainability infrastructure.

---

# Classroom Exercises

## Level 1: Basic Type Hints

Question:

Add Type Hints to this function.

Starter Code:

```python
def greet(name):
    return "Hello, " + name
```

Expected Answer:

```python
def greet(name: str) -> str:
    return "Hello, " + name
```

Explanation:

The function expects a string and returns a string.

Follow-up Question:

Will Python reject `greet(123)` before running the function body?

Expected answer:

No. Type Hints are not runtime checks by default.

## Level 2: Return Value Type

Question:

Make the missing case explicit.

Starter Code:

```python
def find_user(email: str):
    if email == "admin@example.com":
        return User(email=email)

    return None
```

Expected Answer:

```python
def find_user(email: str) -> User | None:
    if email == "admin@example.com":
        return User(email=email)

    return None
```

Explanation:

The function may return a `User` or `None`. The caller must handle both.

## Level 3: `list[T]`

Question:

Improve this signature.

Starter Code:

```python
def get_emails(users: list) -> list:
    return [user.email for user in users]
```

Expected Answer:

```python
def get_emails(users: list[User]) -> list[str]:
    return [user.email for user in users]
```

Explanation:

The input list contains `User` objects. The output list contains strings.

## Level 4: `dict[K, V]`

Question:

Type the status counter.

Starter Code:

```python
def count_statuses(statuses):
    result = {}

    for status in statuses:
        result[status] = result.get(status, 0) + 1

    return result
```

Expected Answer:

```python
def count_statuses(statuses: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}

    for status in statuses:
        result[status] = result.get(status, 0) + 1

    return result
```

Explanation:

The empty dictionary needs help because its key and value types are not obvious.

## Level 5: Optional Value

Question:

Why is this annotation wrong?

Starter Code:

```python
def get_current_user(token: str) -> User:
    if token == "":
        return None

    return User(token=token)
```

Expected Answer:

```python
def get_current_user(token: str) -> User | None:
    if token == "":
        return None

    return User(token=token)
```

Explanation:

The original return type lied. `None` must be part of the contract.

## Level 6: Union

Question:

When is this acceptable, and when is it a smell?

Starter Code:

```python
def parse_user_id(raw: str) -> int | str:
    if raw.isdigit():
        return int(raw)

    return raw
```

Expected Answer:

This can be acceptable when the domain really allows both numeric and external string IDs.
It becomes a smell if callers constantly need complicated branching.

Follow-up Question:

Could a clearer domain model avoid the union?

## Level 7: `TypeVar`

Question:

Fix the generic relationship.

Starter Code:

```python
def identity(value: object) -> object:
    return value
```

Expected Answer:

```python
from typing import TypeVar

T = TypeVar("T")


def identity(value: T) -> T:
    return value
```

Explanation:

`T` preserves the relationship between the input type and output type.

## Level 8: `Generic`

Question:

Design a generic response wrapper.

Starter Code:

```python
class Response:
    def __init__(self, data, error=None):
        self.data = data
        self.error = error
```

Expected Answer:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Response(Generic[T]):
    data: T
    error: str | None = None
```

Explanation:

`Response[User]` and `Response[AgentResult]` preserve payload type while sharing one
wrapper structure.

## Engineering Practice: FastAPI Request and Response Types

Question:

Design types for a user creation endpoint.

Starter Code:

```python
def create_user(payload):
    ...
```

Expected Answer:

```python
from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    email: str
    name: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


def create_user(payload: CreateUserRequest) -> UserResponse:
    ...
```

Explanation:

FastAPI and Pydantic use Type Hints to validate input, serialize output, and generate
OpenAPI documentation.

## Engineering Practice: Playwright Object Types

Question:

Type a helper that logs in using a Playwright page.

Starter Code:

```python
async def login(page, email, password):
    ...
```

Expected Answer:

```python
from playwright.async_api import Page


async def login(page: Page, email: str, password: str) -> None:
    ...
```

Explanation:

The type tells the reader this function expects a `Page`, not a `Browser` or
`BrowserContext`.

## Engineering Practice: AI Backend Message Types

Question:

Define a message type for an AI conversation.

Expected Answer:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
```

Explanation:

AI systems fail when message shape is implicit. Type Hints make the conversation contract
explicit.

---

# FastAPI Connections

FastAPI relies heavily on Type Hints.

## Request Model

```python
from pydantic import BaseModel


class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
```

FastAPI uses this model to:

* parse request body
* validate fields
* report validation errors
* generate OpenAPI schema

## Response Model

```python
class TaskResponse(BaseModel):
    id: int
    title: str
    completed: bool
```

The response model tells clients what the API returns.

## `Depends()`

```python
from fastapi import Depends


def get_current_user(token: str) -> User:
    ...


async def list_tasks(user: User = Depends(get_current_user)) -> list[TaskResponse]:
    ...
```

Type Hints explain dependency output.

FastAPI uses function signatures as API contracts.

```text
function signature
    |
    v
FastAPI introspection
    |
    v
validation + dependency resolution + OpenAPI
```

Tech Lead warning:

If your annotations are wrong, your API documentation and validation assumptions can also
be wrong.

---

# Playwright Connections

Playwright objects have different lifecycle responsibilities.

```text
Browser
    |
    v
BrowserContext
    |
    v
Page
    |
    v
Locator
```

Type Hints help prevent lifecycle confusion.

```python
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Locator, Page


async def create_context(browser: Browser, storage_state: Path) -> BrowserContext:
    return await browser.new_context(storage_state=storage_state)


async def find_submit_button(page: Page) -> Locator:
    return page.get_by_role("button", name="Submit")
```

Production risks without Type Hints:

* passing a `Browser` where a `Page` is expected
* sharing a `BrowserContext` across unrelated jobs
* treating a `Locator` like an immediate element value
* passing storage state as an unstructured dictionary everywhere

Storage state example:

```python
StorageState = dict[str, object]


async def save_storage_state(context: BrowserContext) -> StorageState:
    return await context.storage_state()
```

For larger systems, use a dedicated model or typed alias instead of raw dictionaries
everywhere.

---

# English Interview

## Key Vocabulary

* Type Hint
* annotation
* interface contract
* static type checking
* runtime validation
* type inference
* generic
* `TypeVar`
* `Optional`
* `Union`
* request model
* response model
* tool contract

## Beginner Questions

Question:

Why did Python introduce Type Hints?

Standard Answer:

Python introduced Type Hints to make code easier to understand, analyze, refactor, and
integrate with tools and frameworks while keeping Python dynamically typed.

Question:

Are Type Hints checked at runtime by default?

Standard Answer:

No. Type Hints are not enforced at runtime by default. They are mainly used by humans,
static type checkers, IDEs, and frameworks. Frameworks such as FastAPI and Pydantic can use
annotations for runtime validation.

Question:

Why should parameters and return values be annotated?

Standard Answer:

They define the function's interface contract. Parameters tell callers what to pass, and
return annotations tell callers what to expect.

Question:

What is the difference between `list[T]` and `list`?

Standard Answer:

`list` only tells us the value is a list. `list[T]` also tells us the type of each item.

## Intermediate Questions

Question:

What is the difference between `Optional[User]` and `User | None`?

Standard Answer:

They express the same idea: the value can be a `User` or `None`. `User | None` is the
modern Python syntax.

Question:

Why is `list[User]` better than `list`?

Standard Answer:

Because it preserves item type information. Readers, IDEs, and type checkers know each
item should be a `User`.

Question:

What is Type Inference?

Standard Answer:

Type inference means a tool can infer a variable's type from context without an explicit
annotation.

Question:

Why can IDEs autocomplete better with Type Hints?

Standard Answer:

Because Type Hints tell the IDE what object type a variable has, so it can suggest the
correct methods and attributes.

## Senior Questions

Question:

Explain Type Hints as interface contracts.

Standard Answer:

Type Hints define expectations at function and data boundaries. They describe what a
function accepts and returns, making the interface easier to review, test, refactor, and
integrate with frameworks.

Production Case:

In FastAPI, the same contract can drive request validation, response serialization, and
OpenAPI documentation.

Question:

Explain `Generic` and `TypeVar`.

Standard Answer:

`TypeVar` represents a type variable, and `Generic` lets a class or function preserve type
relationships across different concrete types.

Question:

Why is `T -> T` better than `object -> object`?

Standard Answer:

`object -> object` loses the relationship between input and output. `T -> T` says the
function returns the same type it received, so type information is preserved.

Question:

Why does FastAPI rely heavily on Type Hints?

Standard Answer:

FastAPI introspects function signatures and Pydantic models. Type Hints help FastAPI parse
requests, validate data, resolve dependencies, serialize responses, and generate OpenAPI
documentation.

Question:

How do Type Hints improve AI-assisted development?

Standard Answer:

They give AI tools clearer context about function contracts, message shapes, tool inputs,
tool outputs, and generic response types, which reduces incorrect assumptions during code
generation.

Question:

When should engineers avoid writing Type Hints?

Standard Answer:

Engineers can avoid annotations when local variables are obvious and type inference is
clear. Type Hints should reduce ambiguity, not add visual noise.

---

# Today's Takeaway

Type Hints are not about making Python behave like Java.

They are about making Python boundaries explicit.

```text
Type Hints
    |
    v
Interface Contracts
    |
    +--> humans read faster
    +--> IDEs autocomplete better
    +--> static tools catch more mistakes
    +--> FastAPI generates better APIs
    +--> AI assistants infer intent better
```

Today's most important lessons:

* Type Hints are not runtime checks by default.
* Type Hints are interface contracts.
* Public function parameters and return values should usually be typed.
* `list[T]` is more useful than `list`.
* `User | None` makes missing values explicit.
* `TypeVar` preserves relationships that `object` loses.
* `Generic` is useful for reusable wrappers such as `Response[T]`.
* FastAPI, Playwright, and AI backend systems all benefit from accurate type contracts.
* Do not annotate everything. Annotate where clarity and contract matter.

---

# Before Next Lesson Checklist

Before Day11, confirm you can answer these without looking at the notes:

- [ ] What is a Type Hint?
- [ ] Why are Type Hints interface contracts?
- [ ] Are Type Hints checked at runtime by default?
- [ ] Why should public function parameters be typed?
- [ ] Why should return values be typed?
- [ ] What is the difference between `list` and `list[T]`?
- [ ] What is the difference between `Optional[User]` and `User | None`?
- [ ] When should you use `Union`?
- [ ] What is type inference?
- [ ] Why should empty lists often be annotated?
- [ ] What does `TypeVar` preserve?
- [ ] Why is `T -> T` better than `object -> object`?
- [ ] What problem does `Generic` solve?
- [ ] How does FastAPI use Type Hints?
- [ ] How do Type Hints help Playwright automation code?
- [ ] How do Type Hints improve AI backend tool contracts?
