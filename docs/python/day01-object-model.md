# Lesson 1 — Python Object Model

## Learning Objectives

After completing this lesson, you should be able to:

* Explain why Python became the dominant language for AI and backend automation work.
* Explain Python's design philosophy in terms of readability, object orientation, and developer productivity.
* Explain what it means that everything in Python is an object.
* Explain why functions are objects and why that matters for FastAPI, Playwright, and AI tool systems.
* Implement and explain callable objects using `__call__`.
* Explain why variables store references instead of directly storing objects.
* Explain object identity and the difference between `==` and `is`.
* Explain why mutable default arguments are dangerous.
* Draw a simple memory model for names, references, objects, function objects, and shared mutable state.
* Recognize common bugs caused by identity confusion, reference sharing, and default mutable values.
* Answer beginner, intermediate, and senior-level interview questions about Python's object model.

---

# Why This Matters

Python is not only a scripting language. In modern backend and AI engineering, Python is the coordination language that connects models, APIs, databases, browser automation, queues, vector databases, and deployment tools.

A backend engineer working for an overseas AI startup will often use Python to build systems such as:

* FastAPI services exposing AI features through REST APIs.
* Playwright automation workers that collect, validate, or process web data.
* RAG pipelines that connect documents, embeddings, vector search, and LLM calls.
* Celery or background workers that process long-running AI tasks.
* Internal tools that orchestrate OpenAI API calls, browser sessions, Redis queues, and PostgreSQL storage.

In these systems, Python's object model is not an academic detail. It affects how you design dependencies, how you pass functions around, how you avoid hidden state, how you debug strange bugs, and how you explain your design decisions in an interview.

The most important shift for Day 1 is this:

```text
Python is not mainly about syntax.
Python is a design system built around objects, references, and protocols.
```

If you understand that variables are names bound to objects, functions are first-class objects, and objects can define behavior through special methods, many later topics become much easier:

* Decorators are functions that receive and return function objects.
* Dependency injection in FastAPI depends on callables.
* Playwright's API exposes objects with methods that represent browser state.
* Context managers rely on special methods such as `__enter__` and `__exit__`.
* Iterators and generators rely on object protocols.
* Async programming relies on awaitable objects and event loop coordination.

That is why this lesson starts with the object model. It is the foundation under the rest of the roadmap.

## Roadmap Position

Day 1 is not only a Python lesson. It is the base layer for the entire roadmap.

If you do not understand Python objects and references, later frameworks will look like magic:

```text
Python Object Model
        |
        v
FastAPI Dependency Injection
        |
        v
Playwright Browser Objects
        |
        v
AI Agent Tool Calling
```

The goal today is not to memorize definitions. The goal is to build a mental model that you can reuse again and again:

```text
Name
  |
  v
Reference
  |
  v
Object
  |
  +--> can have attributes
  +--> can have methods
  +--> can be passed around
  +--> can sometimes be called
```

When we later write FastAPI code like this:

```python
def get_current_user() -> str:
    return "user-123"
```

FastAPI does not see "some text in a file." It receives a function object.

When we later write Playwright code like this:

```python
page.get_by_role("button", name="Login").click()
```

`page` is not just a variable. It is a name referring to a live browser page object.

When we later build AI agents, tools are often registered as function objects:

```python
tools = {"search_user": search_user}
```

So Day 1 answers a deeper engineering question:

```text
How does Python let frameworks treat our code as data?
```

## Why Python Became Dominant for AI

Python became dominant in AI for several engineering reasons, not because it is the fastest language.

First, Python optimizes for human speed. AI work involves experimentation: loading data, testing prompts, building prototypes, changing pipelines, and reading unfamiliar code. A language with readable syntax and low ceremony helps teams move quickly. In an AI startup, the first version of a product may change every week. Python makes those changes cheaper.

Second, Python has a strong scientific and machine learning ecosystem. Libraries such as NumPy, pandas, PyTorch, TensorFlow, scikit-learn, FastAPI, Pydantic, SQLAlchemy, Playwright, and many LLM SDKs are built with Python-first workflows. Even when the heavy computation runs in C, C++, CUDA, or Rust, Python often becomes the interface that engineers use to compose the system.

Third, Python is excellent as glue code. Real AI products are rarely just model inference. They require API servers, job queues, databases, authentication, caching, browser automation, document processing, logging, monitoring, and deployment. Python is good at connecting these parts with clear code.

Fourth, Python supports both simple scripts and production systems. You can start with a small script and later evolve it into a package, service, worker, or platform. This is valuable in startups where experiments must become products quickly.

The trade-off is that Python requires discipline. Because it is flexible, it is easy to write messy code. A serious backend engineer must learn the design principles behind Python, not only copy framework examples.

---

# Core Theory

## Python Design Philosophy

Python's design philosophy is often summarized by the phrase "readability counts." The language tries to make code look close to the way engineers think about a problem.

A simple function should look simple:

```python
def calculate_total(price: float, quantity: int) -> float:
    return price * quantity
```

A conditional should be obvious:

```python
if user.is_active:
    send_welcome_email(user)
```

A collection transformation should be readable:

```python
active_users = [user for user in users if user.is_active]
```

Python favors explicitness over hidden magic. It also favors conventions that make code easier to scan. In enterprise backend work, this matters because code is read many more times than it is written. A teammate may need to debug your code during an incident six months after you wrote it. A clear design is a business asset.

However, Python is not anti-abstraction. It supports powerful abstractions through objects, functions, decorators, context managers, iterators, and async protocols. The key is that good Python abstractions should make the code easier to understand, not more impressive.

## Classroom Exercises: Design Philosophy

Question:

Why does Python prefer readability over cleverness?

Think first.

Do not answer "because Python is easy." That is too shallow for an engineering interview.

Expected student answer:

Python code is usually maintained by teams. Readable code reduces onboarding cost, review cost, debugging cost, and production incident risk.

Explanation:

In a startup, speed matters, but messy speed becomes expensive later. Python's design philosophy makes it possible to move quickly while still writing code teammates can understand.

Follow-up question:

If a clever one-line solution and a clear five-line solution both work, which one should you choose in production?

Expected answer:

Choose the clear version unless the clever version has a measurable benefit and is still understandable.

## Everything Is an Object

In Python, everything is an object:

* Integers are objects.
* Strings are objects.
* Lists are objects.
* Dictionaries are objects.
* Functions are objects.
* Classes are objects.
* Modules are objects.
* Exceptions are objects.

An object has three important properties:

```text
Object
+-------------------------+
| identity                |  Who is this object?
| type                    |  What kind of object is this?
| value / state           |  What data does this object hold?
+-------------------------+
```

You can inspect these properties:

```python
value = 42

print(id(value))      # identity
print(type(value))    # type
print(value)          # value
```

The exact number returned by `id()` is implementation-specific. In CPython, it is related to the memory address of the object while it exists. For professional engineering, the important idea is not the exact number. The important idea is that every object has identity.

## Classroom Exercises: Everything Is an Object

Question:

Look at this code:

```python
value = 10
name = "Ada"
items = [1, 2, 3]
```

Which of these are objects?

Think first.

Expected student answer:

All of them. `10` is an integer object, `"Ada"` is a string object, and `[1, 2, 3]` is a list object.

Explanation:

This matters because Python gives a consistent model for all values. Later, when FastAPI inspects type hints or when Playwright returns a `Page` object, you are still working with the same core idea: names refer to objects.

Diagram:

```text
value ----> int object: 10
name  ----> str object: "Ada"
items ----> list object: [1, 2, 3]
```

Follow-up question:

Is a function also an object?

Expected answer:

Yes. A function definition creates a function object.

## Function Objects

A function definition creates a function object and binds a name to it.

```python
def greet(name: str) -> str:
    return f"Hello, {name}"
```

This is not just a block of code. Python creates an object representing the function:

```text
greet
  |
  v
+---------------------------+
| function object           |
| name: greet               |
| code: return f"Hello..."  |
| callable: yes             |
+---------------------------+
```

Because functions are objects, you can assign them to variables:

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

handler = greet

print(handler("Ada"))  # Hello, Ada
```

This is where many beginners get confused:

```python
hello
hello()
```

These are not the same.

`hello` means "the function object itself."

`hello()` means "call the function object now and give me the return value."

```python
def hello() -> str:
    return "Hello"

function_object = hello
return_value = hello()

print(function_object)
print(return_value)
```

Conceptually:

```text
hello
  |
  v
+------------------+
| function object  |
| code: return ... |
+------------------+

hello()
  |
  v
execute function object
  |
  v
"Hello"
```

This distinction is not a small syntax detail. It explains why frameworks can receive your functions and call them later.

FastAPI example:

```python
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

FastAPI needs the function object `health_check`. It should not call `health_check()` immediately when the file is imported. The framework registers the function and calls it later when an HTTP request arrives.

AI Agent example:

```python
tools = {
    "health_check": health_check,
}
```

The dictionary stores the function object. The agent runtime can choose when to call it.

You can pass functions as arguments:

```python
from collections.abc import Callable


def apply_formatter(value: str, formatter: Callable[[str], str]) -> str:
    return formatter(value)


def normalize_email(email: str) -> str:
    return email.strip().lower()

result = apply_formatter("  USER@EXAMPLE.COM ", normalize_email)
print(result)  # user@example.com
```

You can return functions from functions:

```python
from collections.abc import Callable


def build_prefixer(prefix: str) -> Callable[[str], str]:
    def add_prefix(value: str) -> str:
        return f"{prefix}{value}"

    return add_prefix

add_user_prefix = build_prefixer("user:")
print(add_user_prefix("123"))  # user:123
```

This is the foundation for decorators, dependency injection, callbacks, tool calling, and many framework features.

## Classroom Exercises: `hello` vs `hello()`

Question 1:

What is stored in `handler`?

```python
def hello() -> str:
    return "Hello"

handler = hello
```

Think first.

Expected student answer:

`handler` stores a reference to the same function object as `hello`.

Explanation:

No function call happens here. There are no parentheses. We are only binding another name to the function object.

Diagram:

```text
hello   ----+
           |
           v
handler --> function object
```

Question 2:

What is stored in `message`?

```python
def hello() -> str:
    return "Hello"

message = hello()
```

Think first.

Expected student answer:

`message` stores the return value `"Hello"`.

Explanation:

The parentheses call the function. The name `message` does not refer to the function object. It refers to the returned string object.

Diagram:

```text
hello ----> function object ---- call ----> "Hello"
                                      |
                                      v
                                  message
```

Question 3:

Which one should we pass to a framework if we want the framework to call it later?

```python
hello
hello()
```

Expected student answer:

Pass `hello`, not `hello()`.

Explanation:

`hello` gives the framework the callable object. `hello()` executes the function immediately and passes the result.

Progressively harder question:

What is wrong with this tool registry?

```python
def search_user() -> dict[str, str]:
    return {"user_id": "123"}

tools = {
    "search_user": search_user(),
}
```

Expected student answer:

The function is called immediately. The dictionary stores the return value, not the function object.

Correct version:

```python
tools = {
    "search_user": search_user,
}
```

## Callable Objects

An object is callable if you can use parentheses after it:

```python
result = something()
```

Functions are callable, but they are not the only callable objects. Classes are callable because calling a class creates an instance:

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

user = User("Ada")
```

Instances can also be callable if their class defines `__call__`.

```python
class EmailNormalizer:
    def __call__(self, email: str) -> str:
        return email.strip().lower()

normalize_email = EmailNormalizer()

print(normalize_email("  USER@EXAMPLE.COM "))
```

The `__call__` method lets an object behave like a function while still carrying state and configuration.

```python
class RetryPolicy:
    def __init__(self, max_attempts: int) -> None:
        self.max_attempts = max_attempts

    def __call__(self, attempt: int) -> bool:
        return attempt < self.max_attempts

should_retry = RetryPolicy(max_attempts=3)

print(should_retry(1))  # True
print(should_retry(3))  # False
```

Why does this design exist? Because sometimes a plain function is enough, and sometimes you need a function-like object with memory. Python gives you both.

## Variables Store References

A variable in Python does not directly contain the object. A variable is a name bound to a reference to an object.

```python
name = "Ada"
```

Conceptually:

```text
name
  |
  v
+--------+
| "Ada"  |
+--------+
```

When you assign one variable to another, Python copies the reference, not the object.

```python
a = [1, 2, 3]
b = a
```

Memory model:

```text
a ----+
      |
      v
   +-----------+
b ->| [1,2,3]  |
   +-----------+
```

Both `a` and `b` refer to the same list object. If you mutate the object through one name, the other name observes the same change.

```python
a = [1, 2, 3]
b = a

b.append(4)

print(a)  # [1, 2, 3, 4]
print(b)  # [1, 2, 3, 4]
```

This is not a Python bug. It is Python's reference model working as designed.

Variable names can also be deleted.

```python
items = [1, 2, 3]
alias = items

del items

print(alias)  # [1, 2, 3]
```

`del items` deletes the name `items`. It does not necessarily destroy the list object immediately.

Before `del`:

```text
items ----+
         |
         v
alias --> list object: [1, 2, 3]
```

After `del items`:

```text
alias --> list object: [1, 2, 3]
```

The object is still alive because `alias` still refers to it.

Why does this matter?

In backend systems, many names can refer to the same object: a request object, a database session, a Playwright page, a configuration object, or an AI tool registry. Deleting one local name does not automatically destroy the underlying object if other references still exist.

## Classroom Exercises: References and Variable Binding

Question 1:

What does `b` refer to?

```python
a = [1, 2]
b = a
```

Think first.

Expected student answer:

`b` refers to the same list object as `a`.

Diagram:

```text
a ----+
     |
     v
b --> [1, 2]
```

Explanation:

Assignment does not copy the list. It copies the reference.

Question 2:

What is printed?

```python
a = [1, 2]
b = a
b.append(3)
print(a)
```

Expected student answer:

```text
[1, 2, 3]
```

Explanation:

`a` and `b` point to the same mutable object.

Question 3:

What happens here?

```python
page = browser.new_page()
current_page = page
del page
```

Does the browser page object automatically disappear?

Expected student answer:

No. `current_page` still refers to the page object.

Explanation:

This is the same reference model. In Playwright, this matters because browser resources should be closed explicitly. Do not rely on deleting a variable name to clean up external resources.

Question 4:

What is the safer engineering habit for external resources?

Expected student answer:

Close them explicitly with APIs such as `context.close()`, `page.close()`, or context managers when available.

## Object Identity

Object identity answers the question: "Are these two names referring to the exact same object?"

Python uses `is` to compare identity.

```python
a = [1, 2, 3]
b = a
c = [1, 2, 3]

print(a is b)  # True
print(a is c)  # False
```

Memory model:

```text
a ----+
      |
      v
   +-----------+
b ->| [1,2,3]  |
   +-----------+

c ->+-----------+
    | [1,2,3]  |
    +-----------+
```

The lists have equal values, but `a` and `c` are different objects.

## Classroom Exercises: Identity

Question 1:

What is the result?

```python
a = [1, 2, 3]
b = a
c = [1, 2, 3]

print(a is b)
print(a is c)
```

Think first.

Expected student answer:

```text
True
False
```

Explanation:

`a` and `b` point to the same object. `c` points to a different object with the same value.

Diagram:

```text
a ----+
     |
     v
b --> object #1: [1, 2, 3]

c --> object #2: [1, 2, 3]
```

Question 2:

Why does identity matter in real backend systems?

Expected student answer:

Because two objects may represent the same value but still be different runtime objects. This matters for caching, database sessions, browser pages, dependency objects, and shared state.

Explanation:

In PostgreSQL, two Python objects may represent the same database row. In Playwright, two `Page` variables may or may not point to the same live browser tab. In FastAPI, a dependency can return a new object each request or reuse a shared object depending on how it is designed.

## `==` vs `is`

`==` compares value equality.

`is` compares object identity.

```python
a = [1, 2, 3]
b = [1, 2, 3]

print(a == b)  # True: same values
print(a is b)  # False: different objects
```

Use `==` when you care whether two values are equivalent.

Use `is` when you care whether two names refer to the same object.

In production Python, the most common correct use of `is` is checking for `None`:

```python
if user is None:
    raise ValueError("User is required")
```

Why `is None` instead of `== None`? Because `None` is a singleton. There is only one `None` object in the runtime, so identity is the correct check.

```text
user
  |
  v
None singleton object
```

Do not use `is` for string or number comparison:

```python
status = "active"

# Bad
if status is "active":
    ...

# Good
if status == "active":
    ...
```

Some small integers or strings may appear to have the same identity because of interpreter optimizations such as interning. Do not rely on that behavior. It is an implementation detail, not application logic.

## Mutable Default Argument

One of the most famous Python bugs is the mutable default argument bug.

Bad code:

```python
def add_tag(tag: str, tags: list[str] = []) -> list[str]:
    tags.append(tag)
    return tags

print(add_tag("python"))  # ['python']
print(add_tag("fastapi")) # ['python', 'fastapi']  unexpected
```

Why does this happen?

Default argument values are evaluated once when the function is defined, not every time the function is called.

Memory model:

```text
function object: add_tag
+--------------------------------+
| defaults                       |
| tags default ---> list object  |
+--------------------------------+
                       |
                       v
                  +---------+
                  | []      |
                  +---------+
```

First call:

```text
add_tag("python")

tags ---> default list ---> ["python"]
```

Second call:

```text
add_tag("fastapi")

tags ---> same default list ---> ["python", "fastapi"]
```

The same list is reused across calls.

Correct code:

```python
def add_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    if tags is None:
        tags = []

    tags.append(tag)
    return tags
```

Now each call without an explicit list creates a new list.

This rule is important enough to become a professional standard:

```text
Never use a mutable object as a default argument.
Use None as the default, then create the mutable object inside the function.
```

## Classroom Exercises: Mutable Default Arguments

Question 1:

What is printed?

```python
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

print(add_item("a"))
print(add_item("b"))
print(add_item("c"))
```

Think first.

Expected student answer:

```text
['a']
['a', 'b']
['a', 'b', 'c']
```

Explanation:

The same default list is reused across calls.

Diagram:

```text
add_item function object
+--------------------------------+
| default items                  |
|        |                       |
+--------|-----------------------+
         v
      shared list
      []
```

After three calls:

```text
shared list
["a", "b", "c"]
```

Question 2:

Why is this dangerous in FastAPI?

```python
def collect_errors(error: str, errors: list[str] = []) -> list[str]:
    errors.append(error)
    return errors
```

Expected student answer:

If this function is used during request handling, errors from one request can appear in another request because the default list is shared.

Explanation:

This is not only a Python interview trick. It can become a real production data leak.

Request diagram:

```text
Request A ----+
              |
              v
        shared default list
              ^
              |
Request B ----+
```

Question 3:

Fix the function.

Expected student answer:

```python
def collect_errors(error: str, errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []

    errors.append(error)
    return errors
```

Question 4:

Harder version: should this function mutate the input list?

```python
def add_role(role: str, roles: list[str] | None = None) -> list[str]:
    if roles is None:
        roles = []

    roles.append(role)
    return roles
```

Expected student answer:

It depends on the API contract. If callers expect mutation, it is acceptable but should be clear. If callers expect a new list, return a new list instead.

Safer version:

```python
def add_role(role: str, roles: list[str] | None = None) -> list[str]:
    if roles is None:
        roles = []

    return [*roles, role]
```

Explanation:

Senior engineers do not only ask "does this work?" They ask "who owns this object?" and "will this surprise the caller?"

---

# Memory Model

Illustrate what happens in memory.

Use diagrams whenever possible.

Example:

Variable

↓

Reference

↓

Object

## Names, References, and Objects

Python variables are better understood as names.

```python
user_id = 1001
```

```text
+---------+       +-------------+
| user_id | ----> | int object  |
+---------+       | value: 1001 |
                  +-------------+
```

The name `user_id` points to an object. The object has a type, identity, and value.

Assignment creates or rebinds names:

```python
user_id = 1001
user_id = 1002
```

```text
Step 1:

user_id ----> int object 1001

Step 2:

user_id ----> int object 1002

int object 1001 may be reused or garbage collected later.
```

For immutable objects, reassignment creates a new binding. It does not change the original object.

## Shared References

```python
primary_tags = ["python", "backend"]
backup_tags = primary_tags
backup_tags.append("ai")
```

```text
primary_tags ----+
                 |
                 v
              +----------------------------+
backup_tags -->| list: python, backend, ai |
              +----------------------------+
```

Both names point to the same list.

This behavior is useful when intentional. It is dangerous when accidental.

## Function Definition Memory Model

```python
def calculate_score(base: int, bonus: int) -> int:
    return base + bonus
```

```text
calculate_score
      |
      v
+----------------------------+
| function object            |
| __name__: calculate_score  |
| code object                |
| defaults                   |
| annotations                |
+----------------------------+
```

The function object can be passed around just like any other object.

```python
handler = calculate_score
```

```text
calculate_score ----+
                    |
                    v
                 +-----------------+
handler -------->| function object |
                 +-----------------+
```

## Callable Object Memory Model

```python
class Prefixer:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def __call__(self, value: str) -> str:
        return f"{self.prefix}{value}"

add_user_prefix = Prefixer("user:")
```

```text
add_user_prefix
      |
      v
+-----------------------------+
| Prefixer instance           |
| prefix: "user:"             |
| __call__(value)             |
+-----------------------------+
```

Calling the object:

```python
add_user_prefix("123")
```

is conceptually similar to:

```python
add_user_prefix.__call__("123")
```

## Mutable Default Memory Model

```python
def collect_event(event: str, events: list[str] = []) -> list[str]:
    events.append(event)
    return events
```

```text
collect_event function object
+----------------------------------+
| default events reference         |
|          |                       |
+----------|-----------------------+
           v
       +--------+
       | list   |
       | []     |
       +--------+
```

The default list belongs to the function object. It is not recreated per call.

This is why a backend API endpoint, parser, or task function can accidentally leak state across requests if it uses a mutable default argument.

---

# Engineering Thinking

If I were the language designer:

Why would I design it this way?

What trade-offs does this design make?

## Why Make Everything an Object?

If I were designing Python, I would want one consistent mental model. Instead of saying "some things are primitive and some things are objects," Python says nearly everything behaves as an object.

This gives the language consistency:

```python
name = "ada"
print(name.upper())

numbers = [1, 2, 3]
print(numbers.append)

print(len(numbers))
```

Strings have methods. Lists have methods. Functions have attributes. Classes create objects. Objects can implement protocols.

The trade-off is that there is more runtime behavior than in a language with strict compile-time primitives. Python code can be flexible, but flexibility increases the need for tests, type hints, and careful design.

## Why Make Functions Objects?

Functions as objects make Python expressive. Frameworks can accept user-defined behavior without forcing inheritance-heavy designs.

FastAPI can accept a function as a route handler:

```python
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

Playwright can expose methods that return locator objects, and your code can pass helper functions to organize workflows.

AI agent frameworks can register tools as functions:

```python
def search_customer(customer_id: str) -> dict[str, str]:
    return {"customer_id": customer_id, "status": "active"}
```

The trade-off is that engineers must understand what is being passed: a function object, a class, an instance, or a callable object. Otherwise code becomes confusing.

## Why Use References?

References make Python efficient and flexible. Passing a large list or dictionary to a function does not copy the whole object by default.

```python
def add_event(events: list[str], event: str) -> None:
    events.append(event)
```

This function can mutate the original list. That can be useful for performance and shared state.

The trade-off is that accidental mutation is possible. If a function changes an object that the caller still uses, you can create hidden side effects.

Professional Python code handles this trade-off with clear function design:

* Mutating functions should make mutation obvious.
* Pure functions should return new values.
* Shared state should be explicit.
* Mutable defaults should be avoided.
* Type hints should show intent.

## Why Have `==` and `is`?

Python separates value equality from identity because both questions matter.

When comparing user input, API payloads, or database values, you usually care about value equality:

```python
if user.role == "admin":
    ...
```

When checking for sentinel objects such as `None`, you care about identity:

```python
if user is None:
    ...
```

The trade-off is that beginners may confuse the two. A senior engineer should know when identity is meaningful and when it is just an implementation detail.

---

# Engineering Connections

Day 1 matters because modern Python frameworks are built on the object model.

This section is the bridge between today's theory and the rest of the roadmap.

## FastAPI Connections

FastAPI is not magic. It uses function objects, callables, annotations, and dependency objects.

### Route Handler

```python
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

What FastAPI receives:

```text
health_check
      |
      v
+------------------------+
| function object        |
| annotations            |
| return type            |
| callable behavior      |
+------------------------+
      |
      v
FastAPI route table
```

Why Day 1 matters:

If you understand function objects, decorators become less mysterious. `@app.get(...)` registers a function object. It does not simply decorate text.

### `Depends()`

```python
def get_current_user() -> str:
    return "user-123"

@app.get("/me")
def read_me(user_id: str = Depends(get_current_user)) -> dict[str, str]:
    return {"user_id": user_id}
```

Key idea:

```text
Depends(get_current_user)
          |
          v
   stores a callable
          |
          v
FastAPI calls it later during request handling
```

Why this design exists:

FastAPI wants dependencies to be reusable, testable, and replaceable. Passing callables makes that possible.

Classroom question:

Should we write this?

```python
Depends(get_current_user())
```

Think first.

Expected student answer:

No. That calls the function immediately. We should pass `get_current_user`, the function object.

### Realistic FastAPI Example: Request-Scoped Dependency

In a real backend service, a dependency is rarely just a toy function. It often reads headers, validates tokens, opens a database session, or returns the current user.

```python
from typing import Annotated

from fastapi import Depends, Header, HTTPException


class CurrentUser:
    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(authorization: Annotated[str, Header()]) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    return CurrentUser(user_id="user-123", role="admin")
```

Then FastAPI receives the function object:

```python
@app.get("/admin/profile")
def read_admin_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    return {"user_id": current_user.user_id, "role": current_user.role}
```

Classroom question:

Why does FastAPI need `get_current_user` instead of `get_current_user()`?

Expected student answer:

Because FastAPI must call the dependency later for each request. If we call it immediately, there is no request header yet.

Tech Lead follow-up:

If `get_current_user` returned a mutable global user object, what production bug could happen?

Expected student answer:

Different requests could accidentally share user state. Authentication data must be request-scoped, not global mutable state.

## Playwright Connections

Playwright is also object-model heavy.

```python
browser = chromium.launch()
context = browser.new_context()
page = context.new_page()
locator = page.get_by_role("button", name="Login")
```

Object relationship:

```text
Browser
  |
  v
Context
  |
  v
Page
  |
  v
Locator
```

These are not just simple variables. They are names bound to objects that represent live browser state.

Why Day 1 matters:

If two names refer to the same `Page`, actions through either name affect the same browser tab.

```python
page = context.new_page()
login_page = page
```

Diagram:

```text
page -------+
            |
            v
login_page -> Playwright Page object
```

Classroom question:

If `login_page.click(...)` navigates to another URL, what happens to `page`?

Expected student answer:

`page` sees the same navigation because both names refer to the same Page object.

Engineering lesson:

For independent jobs, create independent browser contexts. Do not accidentally share live browser state.

### Realistic Playwright Example: Isolated Login Job

In production automation, you usually want each job to get an isolated browser context.

```python
from playwright.sync_api import Browser


def run_login_check(browser: Browser, email: str, password: str) -> str:
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto("https://example.com/login")
        page.get_by_label("Email").fill(email)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        return page.title()
    finally:
        context.close()
```

Object diagram:

```text
browser
  |
  v
new context for this job
  |
  v
page for this login flow
  |
  v
locators for stable actions
```

Classroom question:

Why not reuse one global `page` object for every login job?

Expected student answer:

Because page state can leak between jobs: cookies, URL, DOM state, form values, and navigation history.

Tech Lead follow-up:

If two scheduled scraping jobs share the same `page` reference, what bug would be hard to debug?

Expected student answer:

One job may navigate the page while another job is reading from it, causing flaky failures and incorrect data extraction.

## AI Agent Connections

AI agents often use tool registration and callback systems.

```python
def search_user(user_id: str) -> dict[str, str]:
    return {"user_id": user_id, "status": "active"}

tools = {
    "search_user": search_user,
}
```

Diagram:

```text
tools
  |
  v
+--------------------------------+
| "search_user" -> function obj  |
+--------------------------------+
```

Why Day 1 matters:

The AI runtime can choose a tool by name, retrieve the function object, and call it later.

```python
tool = tools["search_user"]
result = tool("user-123")
```

Classroom question:

What is wrong here?

```python
tools = {
    "search_user": search_user("user-123"),
}
```

Expected student answer:

It calls the function immediately and stores the result, not the function object.

Engineering lesson:

Tool calling, callbacks, dependency injection, and decorators all depend on the same foundation: functions are objects that can be passed around.

---

# Enterprise Practice

How do real companies use this?

Include examples from:

* FastAPI
* Playwright
* Redis
* PostgreSQL
* Docker
* AI Agent

## FastAPI: Functions as Route Handlers

FastAPI uses Python function objects as route handlers.

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}")
def get_user(user_id: int) -> dict[str, int | str]:
    return {"user_id": user_id, "status": "active"}
```

The decorator `@app.get(...)` receives the function object and registers it in FastAPI's routing system. Conceptually:

```text
get_user function object
        |
        v
FastAPI routing table
+-----------------------------------+
| GET /users/{user_id} -> get_user  |
+-----------------------------------+
```

This is why function objects matter. The framework is not just reading text. It is receiving a real function object with annotations and callable behavior.

FastAPI also uses type hints at runtime for validation, parsing, documentation, and OpenAPI generation. That means Python's object model supports both execution and framework introspection.

## FastAPI: Dependency Injection Uses Callables

FastAPI dependencies are often callables.

```python
from typing import Annotated
from fastapi import Depends, FastAPI

app = FastAPI()


class Settings:
    def __init__(self, environment: str) -> None:
        self.environment = environment


def get_settings() -> Settings:
    return Settings(environment="production")


@app.get("/config")
def read_config(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"environment": settings.environment}
```

`get_settings` is a function object passed to `Depends`. FastAPI calls it when resolving the request.

For configurable dependencies, a callable object can be useful:

```python
class RoleChecker:
    def __init__(self, required_role: str) -> None:
        self.required_role = required_role

    def __call__(self, user_role: str) -> bool:
        return user_role == self.required_role

is_admin = RoleChecker(required_role="admin")
```

The object stores configuration and behaves like a function. That is a clean enterprise pattern when used carefully.

## Playwright: Objects Represent Browser State

Playwright exposes browser automation through objects:

```python
from playwright.sync_api import Page


def login(page: Page, email: str, password: str) -> None:
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
```

Here `page` is a reference to a browser page object. The methods operate on browser state.

```text
page variable
     |
     v
+--------------------+
| Playwright Page    |
| browser connection |
| current DOM state  |
+--------------------+
```

A common enterprise mistake is sharing one browser page object across independent workflows. This can create hidden state bugs. A better design is to create isolated browser contexts for independent tasks.

```python
from playwright.sync_api import Browser


def run_job(browser: Browser, url: str) -> str:
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(url)
        return page.title()
    finally:
        context.close()
```

This code makes lifecycle and state boundaries explicit.

## Redis: References and Serialization Boundaries

Redis stores serialized data outside the Python process. When you put a Python dictionary into Redis, Redis does not store the Python object itself. You serialize it first.

```python
import json
from redis import Redis


def save_user_status(redis: Redis, user_id: str, status: str) -> None:
    payload = {"user_id": user_id, "status": status}
    redis.set(f"user:{user_id}:status", json.dumps(payload))
```

Inside Python:

```text
payload variable -> dict object in Python memory
```

Inside Redis:

```text
key -> JSON string bytes outside Python memory
```

This distinction matters. Mutating the Python dictionary after `redis.set()` does not mutate the Redis value. You must serialize and write again.

## PostgreSQL: Object Identity Is Not Database Identity

A Python object identity is not the same as a database row identity.

```python
class UserRecord:
    def __init__(self, user_id: int, email: str) -> None:
        self.user_id = user_id
        self.email = email

user_a = UserRecord(1, "ada@example.com")
user_b = UserRecord(1, "ada@example.com")

print(user_a is user_b)  # False
```

Both objects may represent the same database row, but they are different Python objects.

```text
user_a -> Python object representing DB row id=1
user_b -> another Python object representing DB row id=1

PostgreSQL row:
+----+-----------------+
| id | email           |
+----+-----------------+
| 1  | ada@example.com |
+----+-----------------+
```

In backend systems, do not confuse:

* Python object identity
* database primary key identity
* business identity such as email or external account ID

They are different concepts.

## Docker: Process Memory Is Isolated

When a Python app runs in Docker, its object memory exists inside a process in a container.

```text
Docker container
+--------------------------------+
| Python process                 |
| names -> references -> objects |
+--------------------------------+
```

If you scale the service to three containers, each container has its own Python memory.

```text
container A: cache dict object
container B: different cache dict object
container C: different cache dict object
```

This is why in-memory state is dangerous for distributed services. Use Redis, PostgreSQL, or another external system for shared state.

## AI Agent: Tools Are Often Function Objects

AI tool calling often maps tool names to Python callables.

```python
from collections.abc import Callable

Tool = Callable[[dict[str, str]], dict[str, str]]


def get_order_status(arguments: dict[str, str]) -> dict[str, str]:
    order_id = arguments["order_id"]
    return {"order_id": order_id, "status": "shipped"}

TOOLS: dict[str, Tool] = {
    "get_order_status": get_order_status,
}
```

Memory model:

```text
TOOLS dict
+-----------------------------------------+
| "get_order_status" -> function object  |
+-----------------------------------------+
```

When the model requests a tool, the backend looks up the function object and calls it.

This is a direct application of Day 1 concepts.

---

# Common Bugs

Typical mistakes.

Why they happen.

How to avoid them.

## Bug 1: Using `is` Instead of `==`

Bad:

```python
status = "active"

if status is "active":
    print("User is active")
```

This may appear to work in some cases because Python may intern some strings. But identity is not value equality.

Good:

```python
if status == "active":
    print("User is active")
```

Use `is` for identity checks such as `None`:

```python
if status is None:
    raise ValueError("Status is required")
```

## Bug 2: Shared List Through Assignment

Bad if accidental:

```python
admin_permissions = ["read", "write"]
default_permissions = admin_permissions

default_permissions.remove("write")

print(admin_permissions)  # ['read']
```

Both names point to the same list.

Good:

```python
admin_permissions = ["read", "write"]
default_permissions = admin_permissions.copy()

default_permissions.remove("write")

print(admin_permissions)      # ['read', 'write']
print(default_permissions)    # ['read']
```

## Bug 3: Mutable Default Arguments

Bad:

```python
def add_error(message: str, errors: list[str] = []) -> list[str]:
    errors.append(message)
    return errors
```

Good:

```python
def add_error(message: str, errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []

    errors.append(message)
    return errors
```

## Bug 4: Hidden Mutation in Helper Functions

Bad:

```python
def add_tracking(payload: dict[str, str]) -> dict[str, str]:
    payload["tracking_id"] = "abc123"
    return payload
```

This mutates the caller's dictionary.

Better if mutation is not expected:

```python
def with_tracking(payload: dict[str, str]) -> dict[str, str]:
    return {**payload, "tracking_id": "abc123"}
```

Now the function returns a new dictionary.

## Bug 5: Confusing Class and Instance Callability

Bad:

```python
class EmailNormalizer:
    def __call__(self, email: str) -> str:
        return email.strip().lower()

normalizer = EmailNormalizer
print(normalizer(" USER@EXAMPLE.COM "))
```

This calls the class, not the instance's `__call__` method. It tries to construct an object and passes the email to `__init__`, which is not what we want.

Good:

```python
normalizer = EmailNormalizer()
print(normalizer(" USER@EXAMPLE.COM "))
```

## Bug 6: Storing Request State in a Global Object

Bad:

```python
request_context: dict[str, str] = {}


def set_current_user(user_id: str) -> None:
    request_context["user_id"] = user_id
```

In a web server, multiple requests may run concurrently. Shared mutable global state can leak data between requests.

Better:

```python
def build_request_context(user_id: str) -> dict[str, str]:
    return {"user_id": user_id}
```

For real request-scoped behavior, use framework-supported dependency injection or context management.

---

# Best Practice

Production-ready implementation.

Explain why it is considered good engineering.

## Prefer Explicit Function Boundaries

A production function should make its inputs, outputs, and side effects clear.

```python
def normalize_email(email: str) -> str:
    return email.strip().lower()
```

This is good because:

* It has a clear name.
* It has type hints.
* It does one thing.
* It has no hidden side effects.
* It is easy to test.

## Avoid Mutable Defaults

Use `None` as the default and initialize inside the function.

```python
def collect_tags(tag: str, tags: list[str] | None = None) -> list[str]:
    if tags is None:
        tags = []

    return [*tags, tag]
```

This version returns a new list instead of mutating the input. That is safer when callers do not expect mutation.

## Make Mutation Intentional

If a function mutates an object, make that obvious through naming and documentation.

```python
def append_audit_event(events: list[str], event: str) -> None:
    events.append(event)
```

The name `append_` signals mutation. The return type `None` also signals that the function changes the input instead of producing a new value.

## Use Callable Objects for Configured Behavior

A callable object is useful when behavior needs configuration.

```python
class MinimumScoreValidator:
    def __init__(self, minimum_score: int) -> None:
        self.minimum_score = minimum_score

    def __call__(self, score: int) -> bool:
        return score >= self.minimum_score

is_qualified = MinimumScoreValidator(minimum_score=80)
```

This is better than a global variable because the configuration is attached to the object.

## Use Type Hints for Public Functions

Type hints make intent visible to humans and tools.

```python
from collections.abc import Callable


def run_validation(value: str, validator: Callable[[str], bool]) -> bool:
    return validator(value)
```

This tells the reader that `validator` must be callable, receive a string, and return a boolean.

## Prefer Readability Over Cleverness

Clever code may save a few lines, but it often costs future debugging time.

Less readable:

```python
result = [f(x) for x in items if (f := lambda value: value.strip().lower())]
```

Readable:

```python
def normalize(value: str) -> str:
    return value.strip().lower()

result = [normalize(item) for item in items]
```

Enterprise code is written for teams, code review, incident response, and onboarding. Clear code wins.

---

# Code Examples

Provide multiple examples.

Start simple.

Increase complexity gradually.

## Example 1: Everything Is an Object

```python
value = 42
name = "Ada"
items = ["python", "fastapi"]

print(type(value))
print(type(name))
print(type(items))

print(value.__class__)
print(name.__class__)
print(items.__class__)
```

Expected idea:

```text
42 is an int object.
"Ada" is a str object.
["python", "fastapi"] is a list object.
```

## Example 2: Function Object

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

print(greet("Ada"))
print(greet.__name__)
print(type(greet))
```

A function is an object with attributes such as `__name__`.

## Example 3: Passing a Function

```python
from collections.abc import Callable


def transform_usernames(
    usernames: list[str],
    transformer: Callable[[str], str],
) -> list[str]:
    return [transformer(username) for username in usernames]


def normalize_username(username: str) -> str:
    return username.strip().lower()

raw_usernames = [" Ada ", "GRACE", " Linus "]
clean_usernames = transform_usernames(raw_usernames, normalize_username)

print(clean_usernames)
```

This pattern appears in data pipelines, validation systems, and tool registries.

## Example 4: Callable Object With `__call__`

```python
class PrefixFormatter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def __call__(self, value: str) -> str:
        return f"{self.prefix}{value}"

format_user_id = PrefixFormatter("user:")
format_order_id = PrefixFormatter("order:")

print(format_user_id("123"))
print(format_order_id("456"))
```

This is useful when you want function-like behavior with stored configuration.

## Example 5: References and Mutation

```python
features = ["login", "billing"]
roadmap = features

roadmap.append("ai-assistant")

print(features)
print(roadmap)
print(features is roadmap)
```

Both names refer to the same list.

## Example 6: Value Equality vs Identity

```python
first = ["python", "fastapi"]
second = ["python", "fastapi"]
third = first

print(first == second)  # True
print(first is second)  # False
print(first is third)   # True
```

Use this example until the difference becomes automatic.

## Example 7: Safe Default Argument

```python
def build_labels(
    primary_label: str,
    extra_labels: list[str] | None = None,
) -> list[str]:
    if extra_labels is None:
        extra_labels = []

    return [primary_label, *extra_labels]

print(build_labels("backend"))
print(build_labels("ai"))
print(build_labels("api", ["fastapi", "python"]))
```

No call leaks state into another call.

## Example 8: FastAPI-Style Dependency

```python
class ApiKeyValidator:
    def __init__(self, valid_keys: set[str]) -> None:
        self.valid_keys = valid_keys

    def __call__(self, api_key: str) -> bool:
        return api_key in self.valid_keys

validator = ApiKeyValidator(valid_keys={"dev-key", "prod-key"})

print(validator("dev-key"))
print(validator("wrong-key"))
```

This mirrors how configured dependencies can be represented as callable objects.

## Example 9: Tool Registry for AI Backend

```python
from collections.abc import Callable

ToolHandler = Callable[[dict[str, str]], dict[str, str]]


def get_weather(arguments: dict[str, str]) -> dict[str, str]:
    city = arguments["city"]
    return {"city": city, "forecast": "sunny"}


def get_order(arguments: dict[str, str]) -> dict[str, str]:
    order_id = arguments["order_id"]
    return {"order_id": order_id, "status": "paid"}

TOOLS: dict[str, ToolHandler] = {
    "get_weather": get_weather,
    "get_order": get_order,
}


def call_tool(name: str, arguments: dict[str, str]) -> dict[str, str]:
    tool = TOOLS[name]
    return tool(arguments)

print(call_tool("get_order", {"order_id": "A100"}))
```

This is Day 1 knowledge applied to AI backend design.

## Classroom Exercises: Progressive Review

These exercises are designed for active recall. Try to answer before reading the explanation.

### Exercise 1: Function Name or Function Call

Question:

What is the difference?

```python
normalize_email
normalize_email(" USER@EXAMPLE.COM ")
```

Expected student answer:

`normalize_email` is the function object. `normalize_email(...)` calls the function and returns a result.

Explanation:

Frameworks need function objects when they want to call your logic later. Application code uses parentheses when it wants the result now.

### Exercise 2: Multiple Names

Question:

What is printed?

```python
def hello() -> str:
    return "hello"

a = hello
b = a

print(b())
```

Expected student answer:

```text
hello
```

Explanation:

`a`, `b`, and `hello` all refer to the same function object.

Diagram:

```text
hello ----+
         |
         v
a ------> function object
         ^
         |
b -------+
```

### Exercise 3: Delete a Name

Question:

Does this still work?

```python
def hello() -> str:
    return "hello"

handler = hello
del hello

print(handler())
```

Expected student answer:

Yes.

Explanation:

`del hello` removes the name `hello`, but `handler` still refers to the function object.

Diagram:

```text
Before del:

hello ----+
         |
         v
handler -> function object

After del:

handler -> function object
```

Engineering connection:

This explains why objects can outlive one local name. In real systems, request objects, browser pages, sessions, and tool functions can all have multiple references.

### Exercise 4: Shared Mutable State

Question:

What is printed?

```python
settings = {"debug": False}
runtime_settings = settings
runtime_settings["debug"] = True

print(settings)
```

Expected student answer:

```text
{"debug": True}
```

Explanation:

Both names refer to the same dictionary object.

Diagram:

```text
settings --------+
                |
                v
runtime_settings -> {"debug": True}
```

Engineering connection:

Shared mutable dictionaries are dangerous when used as global configuration, request context, or temporary storage. Prefer explicit ownership.

### Exercise 5: Mutable Default in an API Helper

Question:

Why is this code dangerous?

```python
def add_audit_event(event: str, events: list[str] = []) -> list[str]:
    events.append(event)
    return events
```

Expected student answer:

The default list is shared across calls, so one request or job can affect another.

Fix:

```python
def add_audit_event(
    event: str,
    events: list[str] | None = None,
) -> list[str]:
    if events is None:
        events = []

    return [*events, event]
```

Explanation:

The safer version avoids both the mutable default bug and unexpected mutation of the caller's list.

---

# Interview Questions

Beginner

Intermediate

Senior

Include follow-up questions.

## Beginner

### 1. What does it mean that everything in Python is an object?

A good answer:

In Python, values such as integers, strings, lists, functions, classes, and modules are objects. Each object has identity, type, and value. Variables are names that reference objects.

Follow-up:

Can you inspect an object's type and identity?

Example answer:

```python
value = 10
print(type(value))
print(id(value))
```

### 2. What is the difference between `==` and `is`?

A good answer:

`==` checks value equality. `is` checks whether two names refer to the same object. I use `==` for normal value comparison and `is` for identity checks, especially `is None`.

Follow-up:

Why should we write `if value is None` instead of `if value == None`?

### 3. Are functions objects in Python?

A good answer:

Yes. A function definition creates a function object. Functions can be assigned to variables, passed as arguments, returned from other functions, and stored in dictionaries.

Follow-up:

How does this relate to FastAPI route handlers?

### 4. What is a mutable default argument bug?

A good answer:

It happens when a mutable object such as a list or dictionary is used as a default argument. The default object is created once when the function is defined, so calls can accidentally share state.

Follow-up:

How do you fix it?

## Intermediate

### 1. Explain variables and references in Python.

A good answer:

A variable is a name bound to a reference to an object. Assignment copies the reference, not necessarily the object. If two names refer to the same mutable object, mutation through one name is visible through the other.

Follow-up:

How would you avoid accidental shared mutation?

### 2. What is a callable object?

A good answer:

A callable object is any object that can be called with parentheses. Functions are callable. Classes are callable. Instances are callable if their class implements `__call__`.

Follow-up:

When would you use `__call__` instead of a plain function?

### 3. Why are function objects important in backend frameworks?

A good answer:

Frameworks can register, inspect, and call user-defined functions. FastAPI uses function objects as route handlers and dependencies. AI tool registries can map tool names to function objects.

Follow-up:

What metadata can frameworks inspect from a function?

### 4. What is object identity?

A good answer:

Object identity is the unique identity of an object during its lifetime. The `is` operator compares identity. Two objects can have equal values but different identities.

Follow-up:

How is Python object identity different from a database primary key?

## Senior

### 1. How can Python's reference model cause production bugs?

A good answer:

Shared references can cause hidden mutation. For example, a helper function may mutate a dictionary that the caller still uses, or a global mutable object may leak request state between users. In concurrent services, shared mutable state can create data leakage and race conditions.

Follow-up:

How would you design APIs to make mutation explicit?

### 2. How does the object model influence dependency injection design?

A good answer:

Dependency injection often depends on callables. A dependency can be a function or a callable object. Function dependencies are simple and stateless. Callable objects are useful when behavior requires configuration. The design should avoid hidden global state and make lifecycle boundaries clear.

Follow-up:

When would a class-based callable dependency be better than a closure?

### 3. Why should a tech lead reject mutable defaults in production code?

A good answer:

Mutable defaults create hidden shared state across calls. In a web service, that can leak data between requests or create non-deterministic bugs. The fix is simple and standardized: use `None` as the default and create the mutable object inside the function.

Follow-up:

Are there any cases where a persistent default object is intentional?

A careful answer:

It is technically possible, but it should almost never be used in application code. If persistent state is needed, it should be explicit, named, tested, and documented.

### 4. How would you explain Python's performance trade-off to a CTO?

A good answer:

Python is not chosen because every operation is fastest. It is chosen because developer productivity, ecosystem strength, and integration speed are high. For AI products, heavy computation often runs in optimized libraries or external services, while Python orchestrates the system. The trade-off is managed through profiling, async I/O, caching, background jobs, and moving hot paths to optimized systems when needed.

Follow-up:

When would you not use Python?

A strong answer:

I would avoid Python for extremely latency-sensitive CPU-bound hot paths, low-level systems code, or high-frequency trading style workloads unless Python is only the orchestration layer.

---

# Tech Lead Review

What would a senior engineer reject?

Why?

How should it be improved?

## Review Case 1: Mutable Default Argument

Rejected code:

```python
def create_user_payload(
    email: str,
    roles: list[str] = [],
) -> dict[str, object]:
    roles.append("user")
    return {"email": email, "roles": roles}
```

Why a tech lead rejects it:

* `roles` is shared across calls.
* The function mutates the list.
* The bug may only appear after multiple requests.
* It violates the coding standard.

Improved code:

```python
def create_user_payload(
    email: str,
    roles: list[str] | None = None,
) -> dict[str, object]:
    if roles is None:
        roles = []

    return {"email": email, "roles": [*roles, "user"]}
```

Why this is better:

* No shared mutable default.
* The returned roles list is new.
* The function is predictable and easy to test.

## Review Case 2: Identity Comparison for Values

Rejected code:

```python
def is_admin(role: str) -> bool:
    return role is "admin"
```

Why a tech lead rejects it:

* `is` checks identity, not value.
* The code may pass locally and fail unpredictably.
* It teaches the wrong mental model.

Improved code:

```python
def is_admin(role: str) -> bool:
    return role == "admin"
```

## Review Case 3: Hidden Mutation

Rejected code:

```python
def prepare_payload(payload: dict[str, str]) -> dict[str, str]:
    payload["source"] = "api"
    return payload
```

Why a tech lead rejects it:

* The function mutates caller-owned data.
* The name does not reveal mutation.
* Hidden mutation makes debugging harder.

Improved code:

```python
def build_payload_with_source(payload: dict[str, str]) -> dict[str, str]:
    return {**payload, "source": "api"}
```

If mutation is intended, use a mutation-revealing name:

```python
def add_source_to_payload(payload: dict[str, str]) -> None:
    payload["source"] = "api"
```

## Review Case 4: Over-Clever Callable

Rejected code:

```python
validator = lambda value: value.strip().lower() in {"yes", "true", "1"}
```

This is not always terrible, but in production code a named function is often better.

Improved code:

```python
def is_truthy_string(value: str) -> bool:
    normalized_value = value.strip().lower()
    return normalized_value in {"yes", "true", "1"}
```

Why this is better:

* It is easier to test.
* It is easier to search.
* It gives the behavior a name.
* It is clearer during code review.

## Tech Lead Follow-up Questions

These are the questions a senior engineer may ask after the first answer is already correct.

### Follow-up 1: Ownership

Question:

Who owns this object?

Why it matters:

Many Python bugs come from unclear ownership. If a function receives a list or dictionary, the caller and callee must have the same expectation: mutate it or return a new object.

Expected student answer:

If mutation is intended, the function name and return type should make that clear. If mutation is not intended, the function should return a new object.

### Follow-up 2: Lifecycle

Question:

Who closes this object?

Why it matters:

For normal Python objects, garbage collection may eventually clean up memory. For external resources such as browser contexts, database sessions, files, or network connections, cleanup must be explicit.

Expected student answer:

The code that creates the external resource should usually define the cleanup boundary, often with `try/finally` or a context manager.

### Follow-up 3: Framework Timing

Question:

Should this function be called now, or should the framework call it later?

Why it matters:

This is the core of `hello` vs `hello()`. FastAPI dependencies, callbacks, and AI tools often need the function object now so the framework can call it later.

Expected student answer:

If the framework needs reusable behavior, pass the function object. If application code needs the result immediately, call the function.

### Follow-up 4: Shared State

Question:

Can two requests or jobs accidentally share this object?

Why it matters:

Shared mutable state is one of the fastest ways to create production bugs in web APIs, browser automation, and AI agent systems.

Expected student answer:

Request-specific state should be created per request or per job. Shared state should be explicit, thread-safe if needed, and usually stored in external systems like Redis or PostgreSQL.

---

# CTO Thinking

If I were reviewing this architecture,

would I approve it?

Explain the reasoning.

## Architecture Question

Should an AI backend platform use Python as the main application language?

A CTO-level answer should not be emotional. It should discuss trade-offs.

I would approve Python as the main application language for many AI backend systems if the system is primarily I/O-bound, integration-heavy, and dependent on the AI ecosystem.

Reasons to approve:

* Python has the strongest AI and data ecosystem.
* Python is productive for small teams.
* FastAPI can support clean API development.
* Python integrates well with OpenAI APIs, vector databases, Redis, PostgreSQL, Playwright, Celery, and workflow tools.
* Most AI product bottlenecks are network calls, model inference, database access, or external services, not pure Python CPU execution.

Risks:

* CPU-bound Python code can become slow.
* Dynamic typing can become messy without type hints and tests.
* Shared mutable state can cause subtle bugs.
* Poor project structure can turn prototypes into unmaintainable systems.

Controls:

* Use type hints for public functions.
* Use Black and Ruff.
* Use Pydantic models for API boundaries.
* Use dependency injection instead of global mutable state.
* Use Redis or PostgreSQL for shared state.
* Use background workers for long-running jobs.
* Profile before optimizing.
* Move hot paths to optimized libraries or services when necessary.

Final CTO decision:

```text
Approved, if Python is used with production engineering discipline.
Not approved, if the team treats Python as a collection of scripts with no boundaries, tests, or standards.
```

The lesson from Day 1 is that Python's flexibility is a strength only when engineers understand the object model and design with discipline.

---

# English for Interviews

Useful technical English.

Key vocabulary.

Example answers.

This section is intentionally short. Use it to practice overseas interview expression after you already understand the engineering reasoning in Chinese.

Do not memorize these sentences mechanically. Use them as patterns.

## Key Vocabulary

* object model
* reference
* identity
* equality
* callable
* function object
* mutable object
* immutable object
* default argument
* shared state
* side effect
* dependency injection
* route handler
* hidden mutation
* implementation detail
* runtime behavior
* trade-off

## Useful Expressions

```text
In Python, variables are names bound to object references.
```

```text
The `==` operator compares values, while `is` compares identity.
```

```text
A function is a first-class object, so it can be passed around like any other value.
```

```text
A callable object is useful when we need function-like behavior with configuration or state.
```

```text
Mutable default arguments are dangerous because the default object is created once at function definition time.
```

```text
In production code, I prefer explicit boundaries and avoid hidden shared mutable state.
```

## Example Interview Answer: Python Object Model

Question:

What does it mean that everything in Python is an object?

Answer:

In Python, values such as integers, strings, lists, functions, and classes are objects. Each object has identity, type, and value. Variables do not directly store the object; they are names bound to references. This design makes Python consistent and flexible. For example, functions are objects, so frameworks like FastAPI can register route handlers and dependency functions.

## Example Interview Answer: `==` vs `is`

Question:

What is the difference between `==` and `is`?

Answer:

`==` checks whether two objects are equal in value. `is` checks whether two references point to the exact same object. In application code, I use `==` for value comparison, such as checking a status string, and `is` for identity checks such as `value is None`.

## Example Interview Answer: Mutable Defaults

Question:

Why are mutable default arguments dangerous?

Answer:

Default argument values are evaluated once when the function is defined. If the default is a mutable object like a list or dictionary, all calls that use the default share the same object. This can leak state across calls. The standard solution is to use `None` as the default and create a new list or dictionary inside the function.

## Example Interview Answer: Python for AI

Question:

Why is Python widely used in AI backend systems?

Answer:

Python is widely used because it is readable, productive, and has a strong AI ecosystem. Many heavy computations are handled by optimized libraries or external model services, while Python orchestrates APIs, databases, queues, vector search, and model calls. The trade-off is that teams must use engineering discipline: type hints, tests, clear architecture, and careful state management.

---

# Cheat Sheet

One-page summary.

Only the most important points.

## Day 1 Summary

```text
Python = objects + references + protocols + readable design
```

## Everything Is an Object

Every value has:

```text
identity + type + value
```

Examples:

```python
type(42)
type("Ada")
type([1, 2, 3])
type(lambda value: value)
```

## Function Objects

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

handler = greet
handler("Ada")
```

A function can be:

* assigned to a variable
* passed as an argument
* returned from another function
* stored in a dictionary
* inspected by frameworks

## Callable Objects

```python
class Normalizer:
    def __call__(self, value: str) -> str:
        return value.strip().lower()

normalize = Normalizer()
normalize(" USER ")
```

## Variables Store References

```python
a = [1, 2]
b = a
b.append(3)
print(a)  # [1, 2, 3]
```

Diagram:

```text
a ----+
      v
b -> [1, 2, 3]
```

## `==` vs `is`

```python
[1, 2] == [1, 2]  # True
[1, 2] is [1, 2]  # False
```

Use:

```python
value == "active"   # value equality
value is None       # identity check
```

## Mutable Default Rule

Never:

```python
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items
```

Always:

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

## Enterprise Rule

```text
Avoid hidden shared mutable state.
Make dependencies explicit.
Make mutation obvious.
Use type hints.
Prefer readable code.
```

---

# Homework

Coding exercise.

Thinking exercise.

Reading assignment.

## Coding Exercise 1: Function Object Registry

Create a file locally named `tool_registry.py` and implement a small tool registry.

Requirements:

* Use Python 3.12+ syntax.
* Use type hints.
* Define at least three tool functions.
* Store them in a dictionary.
* Implement `call_tool(name: str, arguments: dict[str, str]) -> dict[str, str]`.
* Raise a meaningful error if the tool does not exist.

Example tools:

* `get_user_status`
* `normalize_email`
* `calculate_score`

Engineering goal:

Understand that functions can be stored and called dynamically.

## Coding Exercise 2: Callable Object

Implement a class called `PrefixFormatter`.

Requirements:

* The constructor accepts `prefix: str`.
* The class implements `__call__(self, value: str) -> str`.
* Calling the object returns the prefix plus the value.
* Write at least three examples.

Example:

```python
format_user_id = PrefixFormatter("user:")
print(format_user_id("123"))  # user:123
```

Engineering goal:

Understand when an object can behave like a function.

## Coding Exercise 3: Fix Mutable Default Bug

Given this bad code:

```python
def add_event(event: str, events: list[str] = []) -> list[str]:
    events.append(event)
    return events
```

Tasks:

* Explain the bug in your own words.
* Draw the memory model.
* Rewrite the function safely.
* Write three calls that prove the bug is fixed.

## Thinking Exercise 1

A teammate writes this code:

```python
def enrich_payload(payload: dict[str, str]) -> dict[str, str]:
    payload["source"] = "api"
    return payload
```

Questions:

* Does this function mutate the caller's dictionary?
* Is that obvious from the function name?
* How would you rewrite it if mutation is not intended?
* How would you rename it if mutation is intended?

## Thinking Exercise 2

Explain this statement:

```text
Python is productive because it is flexible, but production Python requires discipline.
```

Your answer should mention:

* type hints
* tests
* readability
* shared mutable state
* framework usage

## Reading Assignment

Read these concepts again before Day 2:

* object identity
* references
* mutable objects
* immutable objects
* copying
* deep copying

Day 2 will build directly on this lesson.

---

# Definition of Done

The lesson is complete only if the student can:

* Explain the concept.
* Solve the exercise.
* Pass interview questions.
* Apply it in a project.

For Day 1, the student is done only when they can:

* Explain why Python is dominant in AI backend work.
* Explain Python's design philosophy without only saying "easy syntax."
* Explain that everything in Python is an object.
* Explain that functions are objects.
* Pass a function as an argument and explain why it works.
* Implement a callable object using `__call__`.
* Draw the names-references-objects memory model.
* Explain object identity.
* Correctly choose between `==` and `is`.
* Explain the mutable default argument bug from memory.
* Fix mutable default argument code using `None`.
* Identify hidden mutation in a code review.
* Explain how these ideas appear in FastAPI and Playwright.
* Answer at least three beginner, three intermediate, and two senior interview questions from this lesson.
* Complete the homework exercises.

---

# Related Topics

Previous lesson:

None. This is the first lesson.

Next lesson:

Day 2 — Mutable vs Immutable

Future connections:

FastAPI

Playwright

Docker

Redis

AI Agent

## How This Lesson Connects Forward

FastAPI:

* Route handlers are function objects.
* Dependencies are callables.
* Type hints are used for validation and documentation.
* Request state must not leak through mutable defaults or global mutable objects.

Playwright:

* Browser, context, page, and locator are objects.
* References to browser objects represent live external state.
* Automation code must avoid accidental shared state between jobs.

Docker:

* Python object memory exists inside one process in one container.
* Multiple containers do not share Python objects.
* Shared state belongs in external systems.

Redis:

* Redis stores serialized data, not Python object references.
* Use Redis for shared state across processes.

AI Agent:

* Tools can be represented as function objects.
* Tool registries often map names to callables.
* Callable objects can store configuration for tool behavior.

---

# Classroom Discussion

The important classroom discussion today was not "what is the syntax?"

The real discussion was:

```text
When I write a name in Python, what does that name point to?
```

That question explains almost everything in this lesson.

When we wrote:

```python
handler = hello
```

we were not copying code. We were binding another name to the same function object.

When we wrote:

```python
message = hello()
```

we were calling the function and binding the name to the return value.

When we wrote:

```python
b = a
```

we were not copying the object. We were copying the reference.

When we wrote:

```python
del a
```

we were deleting a name, not necessarily destroying the object.

The engineering discussion is this:

```text
Names are cheap.
Objects have identity.
Mutable objects can be shared.
Frameworks can receive function objects and call them later.
```

This is why a backend engineer must think beyond syntax. The same mental model will appear in dependency injection, browser automation, tool calling, context managers, async tasks, and production debugging.

## From Today's Lesson to Tomorrow

Today we learned that variables are names bound to object references.

Tomorrow we ask the next question:

```text
What kind of object is safe to share?
```

That is the bridge to Day 2: Mutable vs Immutable.

Day 1 gives us the model:

```text
name -> reference -> object
```

Day 2 will ask:

```text
Can this object change after it is created?
```

This matters because:

* FastAPI request data should not accidentally leak between requests.
* Playwright browser state should not accidentally leak between jobs.
* AI Agent tool inputs and outputs should be predictable.
* Redis and PostgreSQL boundaries require clear serialization and ownership.

If Day 1 is about "what does this name point to?", Day 2 is about "can the thing it points to change?"

That is the next layer of engineering thinking.

---

# Notes

Additional thoughts.

Interesting discoveries.

Future improvements.

## Notes for Future Editions

This first edition focuses on Python's object model as an engineering foundation. Future editions can add:

* More diagrams comparing mutable and immutable objects.
* A small FastAPI demo showing route handler registration.
* A Playwright example showing why browser contexts should be isolated.
* A mini AI tool-calling project built from function objects.
* A quiz section with answers.

## Final Thought

Python gives backend engineers a powerful combination: readable code, flexible objects, first-class functions, and a huge AI ecosystem. The price of that power is responsibility. If you understand references, identity, callables, and mutable state, you are no longer just writing Python syntax. You are beginning to think like a Python backend engineer.
