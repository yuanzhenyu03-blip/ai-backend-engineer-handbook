# Lesson 4 — Scope & LEGB

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day03 — Functions & Parameter Passing

Next Lesson: Day05 — Closures

---

# Why This Matters

Scope is the rule system Python uses to answer one question:

```text
When I write a name, where does Python look for it?
```

That sounds small, but backend systems are built from functions that call other functions,
factories that create dependencies, closures that preserve configuration, and workers that
run code later.

If an engineer does not understand scope, these bugs become common:

* A function accidentally reads a global variable.
* A FastAPI dependency leaks request state.
* A Playwright job reuses a global page object.
* An AI backend shares conversation state across users.
* A closure returns the wrong value because of late binding.
* A nested function cannot update an outer variable without `nonlocal`.

Day04 is where the Python object model becomes function design.

Day01 taught:

```text
name -> reference -> object
```

Day02 taught:

```text
Some objects can mutate.
```

Day03 taught:

```text
Function parameters are local names.
```

Day04 asks:

```text
Which scope does this name belong to?
```

This is why scope matters in production. Names are not floating in the air. Python resolves
them using a deterministic rule called LEGB.

---

# Roadmap Position

Day04 builds directly on function boundaries.

```text
Day01: Object Model
        |
        v
Day02: Mutable vs Immutable
        |
        v
Day03: Functions & Parameter Passing
        |
        v
Day04: Scope & LEGB
        |
        v
Day05: Closures
        |
        v
FastAPI / Playwright / AI Backend Factories
```

Day04 explains where names are found.

Day05 will go deeper into closures, decorators, and function factories. Without Day04,
closures look like magic. With Day04, closures become a natural result of lexical scope
and captured environments.

---

# Lesson Map

Today's Lesson

1. Why Scope Matters
2. LEGB
3. Lexical Scope vs Dynamic Scope
4. Local vs Global
5. `global`
6. `nonlocal`
7. Mutation vs Rebinding
8. Closure
9. Late Binding
10. FastAPI Connections
11. Playwright Connections
12. AI Backend Connections
13. Interview Review
14. Today's Takeaway

---

# Estimated Study Time

Reading: 90-120 minutes

Exercises: 60-90 minutes

Coding: 45-60 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Explain LEGB: Local, Enclosing, Global, Built-in.
* Explain Python name lookup.
* Explain lexical scope and why Python does not use dynamic scope.
* Explain why `UnboundLocalError` happens.
* Explain when `global` works and why it is risky.
* Explain when `nonlocal` is needed.
* Explain mutation vs rebinding in scope problems.
* Define closure as function object plus captured environment.
* Explain late binding and fix it with default arguments.
* Connect scope rules to FastAPI, Playwright, and AI backend systems.

---

# Main Concepts

## LEGB

LEGB is Python's name lookup order:

```text
L -> Local
E -> Enclosing
G -> Global
B -> Built-in
```

When Python sees a name, it searches in this order:

```text
Current function local scope
        |
        v
Enclosing function scopes
        |
        v
Module global scope
        |
        v
Python built-in scope
```

Example:

```python
name = "global"


def outer() -> None:
    name = "enclosing"

    def inner() -> None:
        name = "local"
        print(name)

    inner()
```

Output:

```text
local
```

`inner()` finds `name` in its local scope first.

If we remove the local name:

```python
name = "global"


def outer() -> None:
    name = "enclosing"

    def inner() -> None:
        print(name)

    inner()
```

Output:

```text
enclosing
```

Now `inner()` cannot find `name` locally, so it looks in the enclosing scope.

If we remove the enclosing name:

```python
name = "global"


def outer() -> None:
    def inner() -> None:
        print(name)

    inner()
```

Output:

```text
global
```

Now Python finds `name` in the module global scope.

If none of those scopes contain the name, Python checks built-ins:

```python
print(len([1, 2, 3]))
```

`len` is found in built-in scope.

## Lexical Scope

Python uses lexical scope.

That means a function searches for names based on where the function is defined,
not where the function is called.

This was one of the most important classroom points today.

```text
Python name lookup depends on definition location.
Python name lookup does not depend on call location.
```

Example:

```python
message = "global"


def outer() -> callable:
    message = "from outer"

    def inner() -> str:
        return message

    return inner


func = outer()


def caller() -> str:
    message = "from caller"
    return func()


print(caller())
```

Output:

```text
from outer
```

Why?

`inner()` was defined inside `outer()`. Its enclosing scope is `outer()`, not `caller()`.

Diagram:

```text
Definition structure:

global scope
  |
  +-- outer()
  |     |
  |     +-- inner()
  |
  +-- caller()

inner searches:

inner local -> outer enclosing -> global -> built-in
```

`caller()` does not become the enclosing scope just because it calls `func()`.

That would be dynamic scope. Python does not use that model.

## Lexical Scope vs Dynamic Scope

Lexical scope:

```text
Look up names by where the function is written.
```

Dynamic scope:

```text
Look up names by who called the function.
```

Python chose lexical scope because it makes code more predictable.

If Python used dynamic scope, a function's behavior could change depending on who calls it.

That would create hidden dependencies and unpredictable production behavior.

Engineering comparison:

| Model | Name lookup depends on | Production impact |
|-------|------------------------|-------------------|
| Lexical scope | Where code is defined | Predictable, reviewable |
| Dynamic scope | Call stack at runtime | Hidden dependencies, surprising behavior |

Tech Lead rule:

```text
A function should be understandable from its definition and explicit inputs.
```

## Local vs Global

Consider this code:

```python
count = 0


def add() -> None:
    count = count + 1
```

This raises:

```text
UnboundLocalError
```

Why?

Python decides at compile time that `count` is a local variable inside `add()` because
there is an assignment to `count` in the function body.

Inside the function, Python reads the line as:

```text
local count = local count + 1
```

But the local `count` does not have a value yet.

Diagram:

```text
global scope:

count -> 0

function add local scope:

count -> not assigned yet
```

Python does not say:

```text
Use global count for the right side, then local count for the left side.
```

It treats `count` as local throughout the function unless told otherwise.

## `global`

`global` tells Python that a name should be bound in the module global scope.

```python
count = 0


def add() -> None:
    global count
    count = count + 1


add()
print(count)
```

Output:

```text
1
```

Why it works:

```text
global count
```

tells Python:

```text
Do not treat count as a local name.
Use the module-level count.
```

But this is usually not what we want in backend systems.

Global variables are shared across requests, jobs, users, and sessions inside the same process.

Bad FastAPI-style state:

```python
current_user_id: str | None = None
```

This is dangerous because request-specific state must not live in a global variable.

Engineering rule:

```text
Use global for constants rarely.
Do not use global for request state.
```

## `nonlocal`

`nonlocal` tells Python to bind a name in the nearest enclosing function scope.

Example:

```python
def outer():
    count = 0

    def inner():
        nonlocal count
        count += 1
        return count

    return inner
```

`count` lives in `outer()`.

`inner()` wants to rebind `count`.

Without `nonlocal`, Python would treat `count` as local inside `inner()`, and `count += 1`
would raise `UnboundLocalError`.

Diagram:

```text
outer scope:

count -> 0
   ^
   |
inner uses nonlocal count
```

`nonlocal` exists because closures sometimes need private state.

It is useful, but it should be used carefully. Too much `nonlocal` can create hidden mutable state.

## Mutation vs Rebinding

This was another key classroom distinction.

Rebinding changes which object a name points to.

Mutation changes the object itself.

Example:

```python
count += 1
```

For an integer, this means:

```text
count = count + 1
```

It creates a new integer object and rebinds the name `count`.

That is why `global` or `nonlocal` may be needed if `count` belongs to another scope.

Now compare:

```python
x.append(1)
```

This does not rebind `x`.

It mutates the list object that `x` already points to.

Diagram:

```text
Rebinding:

count -> 0

count += 1

count -> 1

Mutation:

x -> [ ]

x.append(1)

x -> [1]
```

That is why `append()` does not require `global` or `nonlocal` if the name is only read
from an outer scope.

Example:

```python
items = []


def add_item() -> None:
    items.append(1)
```

This works because `items` is not rebound.

But this does not:

```python
items = []


def add_item() -> None:
    items = items + [1]
```

Here `items` is rebound, so Python treats it as local.

## Closure

A closure is not simply "a function inside another function."

Engineering definition:

```text
Closure = Function Object + Captured Environment
```

The function object remembers variables from the scope where it was defined.

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

Use it:

```python
counter = make_counter()

print(counter())
print(counter())
print(counter())
```

Output:

```text
1
2
3
```

Why does this work after `make_counter()` has already returned?

Because `counter` is a function object that captured its environment.

Diagram:

```text
make_counter() call:

count -> 0

returns:

counter function object
  |
  v
captured environment:
count -> 0, then 1, then 2, then 3
```

The outer function returned, but the captured environment is still alive because the returned
function object needs it.

This is important for dependency factories, prompt builders, and configured callbacks.

## Late Binding

Late binding means a closure looks up the variable when the function is called,
not when the function is created.

Example:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

Test it:

```python
funcs = make_funcs()

print(funcs[0]())
print(funcs[1]())
print(funcs[2]())
```

Output:

```text
2
2
2
```

Why?

All three functions capture the same variable `i`.

After the loop finishes, `i` is `2`.

Diagram:

```text
f0 ----+
      |
f1 ----+--> captured variable i -> 2
      |
f2 ----+
```

The default argument solution:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f(i=i):
            return i

        funcs.append(f)

    return funcs
```

Now:

```python
funcs = make_funcs()

print(funcs[0]())
print(funcs[1]())
print(funcs[2]())
```

Output:

```text
0
1
2
```

Why?

Default argument values are evaluated when the function is defined.

Each function gets its own default value for `i`.

---

# Engineering Thinking

## Why Python Chose Lexical Scope

Lexical scope makes code review possible.

A Tech Lead can read a function definition and understand where names come from.

If Python used dynamic scope, a function could behave differently depending on the caller.

That would make production behavior harder to predict.

Comparison:

```text
Lexical scope:

Where was this function defined?

Dynamic scope:

Who called this function today?
```

Python chose the model that favors readability and predictable reasoning.

## Production Risks

Scope bugs can create production incidents:

* Hidden dependencies on globals
* Unpredictable behavior from shadowed names
* Shared mutable state between requests
* Race conditions in background tasks
* State pollution in AI conversations
* Browser state leakage in Playwright workers
* Late-binding bugs in callback generation

## Tech Lead Review

A senior engineer would ask:

* Is this function reading hidden global state?
* Is request-specific data stored globally?
* Does this closure capture mutable state?
* Could this callback suffer from late binding?
* Is `global` or `nonlocal` necessary, or is there a cleaner design?
* Is mutation intentional and visible from the function name?

## CTO Thinking

A CTO cares because hidden state creates system risk.

Scope bugs are not only local code bugs. They can become:

* privacy issues
* user data leaks
* unreliable automation jobs
* hard-to-debug AI behavior
* scaling problems across workers

Architecture should keep state ownership explicit.

---

# Classroom Exercises

## Exercise 1: LEGB Lookup

Question:

What prints?

```python
name = "global"


def outer():
    name = "enclosing"

    def inner():
        print(name)

    inner()


outer()
```

Think first.

Expected Answer:

```text
enclosing
```

Explanation:

`inner()` has no local `name`, so Python looks in the enclosing scope and finds `name`
inside `outer()`.

## Exercise 2: Lexical Scope

Question:

Why does this print `"outer"` instead of `"caller"`?

```python
def outer():
    value = "outer"

    def inner():
        return value

    return inner


func = outer()


def caller():
    value = "caller"
    return func()


print(caller())
```

Expected Answer:

```text
outer
```

Explanation:

Python uses lexical scope. `inner()` searches based on where it was defined, not where it
was called.

## Exercise 3: UnboundLocalError

Question:

Why does this fail?

```python
count = 0


def add():
    count = count + 1
```

Expected Answer:

Python treats `count` as a local variable inside `add()` because the function assigns to it.
Then it tries to read local `count` before it has a value.

Explanation:

This is compile-time local variable determination.

## Exercise 4: `global`

Question:

How can this be made to work?

```python
count = 0


def add():
    count = count + 1
```

Expected Answer:

```python
count = 0


def add():
    global count
    count = count + 1
```

Explanation:

`global count` tells Python to bind `count` in module global scope.

Follow-up:

Should this be used for request state in FastAPI?

Expected Answer:

No. Request state should not be stored globally.

## Exercise 5: `nonlocal`

Question:

Why is `nonlocal` needed?

```python
def outer():
    count = 0

    def inner():
        nonlocal count
        count += 1
        return count

    return inner
```

Expected Answer:

`inner()` rebinding `count` must target the nearest enclosing scope.

Explanation:

Without `nonlocal`, Python would treat `count` as local inside `inner()`.

## Exercise 6: Mutation vs Rebinding

Question:

Why does this work without `global`?

```python
items = []


def add():
    items.append(1)
```

Expected Answer:

Because `append()` mutates the list object. It does not rebind the name `items`.

Explanation:

Python can find `items` in global scope and mutate the object.

## Exercise 7: Closure Counter

Question:

Why does this print `1`, `2`, `3`?

```python
counter = make_counter()

print(counter())
print(counter())
print(counter())
```

Expected Answer:

`counter` is a function object with a captured environment containing `count`.

Explanation:

The outer function already returned, but the returned function still preserves access to
the captured `count`.

## Exercise 8: Late Binding

Question:

Why do these functions all return `2`?

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

Expected Answer:

The functions capture the same variable `i`, and after the loop finishes `i` is `2`.

Explanation:

Closures use late binding. The variable is looked up when the function is called.

---

# FastAPI Connections

FastAPI uses functions heavily:

* route handlers
* dependencies
* dependency factories
* background tasks
* database session providers

Scope rules affect all of them.

## Dependency Injection and `Depends()`

Example:

```python
from fastapi import Depends, FastAPI

app = FastAPI()


def get_prefix() -> str:
    return "user"


@app.get("/profile")
def read_profile(prefix: str = Depends(get_prefix)) -> dict[str, str]:
    return {"prefix": prefix}
```

FastAPI receives the function object `get_prefix`.

The dependency function should use explicit inputs and request-scoped state, not hidden
global request variables.

## Request Lifecycle

Bad design:

```python
current_user_id: str | None = None
```

This is global request state.

If many requests are handled by the same process, this can cause user state pollution.

Better design:

```python
def get_current_user_id() -> str:
    return "user-123"
```

In real applications, the dependency would read from the request, token, or database session.

## Background Tasks

Closures can be useful for configured background behavior, but captured mutable state must
be reviewed carefully.

```python
def make_task(user_id: str):
    def task() -> str:
        return user_id

    return task
```

This captures `user_id` safely as a value.

But capturing mutable request state can be dangerous if it is shared or changes later.

## Database Sessions

Database sessions should be request-scoped.

Do not store a request's session object in a global variable.

Engineering rule:

```text
FastAPI dependencies should make scope and lifecycle explicit.
```

---

# Playwright Connections

Playwright exposes browser automation state through objects:

* `Browser`
* `BrowserContext`
* `Page`
* `Locator`

These objects have lifecycles.

Scope mistakes create automation bugs.

Bad design:

```python
page = None


async def run_job(keyword: str) -> None:
    await page.fill("#search", keyword)
```

The function depends on a hidden global `page`.

This is risky because jobs can interfere with each other.

Better design:

```python
async def run_job(context, keyword: str) -> None:
    page = await context.new_page()
    try:
        await page.fill("#search", keyword)
    finally:
        await page.close()
```

Here the page lifecycle is local to the job.

Engineering rule:

```text
Playwright page objects should not be global.
Browser state should be scoped to the job that owns it.
```

Closures can be useful for Playwright factories:

```python
def make_login_job(email: str, password: str):
    async def login(page) -> None:
        await page.fill("#email", email)
        await page.fill("#password", password)

    return login
```

This captures configuration. It should not capture shared mutable page state.

---

# AI Backend Connections

AI backend systems use scope in factories, prompt builders, and dependency creators.

## Session State

Bad design:

```python
messages: list[dict[str, str]] = []
```

This is global conversation state.

Multiple users can accidentally share it.

Better design:

```python
def build_messages(user_input: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": user_input}]
```

For real systems, store session state per user/session in a database or cache.

## LLM Factory Functions

Closures can build configured functions:

```python
def make_prompt_builder(system_prompt: str):
    def build(user_input: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

    return build
```

This is a closure:

```text
build function object + captured system_prompt
```

This is useful because the configuration is preserved without global variables.

Engineering rule:

```text
Use closures for stable configuration.
Avoid closures that hide shared mutable user state.
```

---

# English Interview

## Key Vocabulary

* lexical scope
* dynamic scope
* local scope
* enclosing scope
* global scope
* built-in scope
* closure
* captured environment
* rebinding
* mutation
* `global`
* `nonlocal`
* late binding

## Beginner Questions

Question:

What is LEGB in Python?

Model Answer:

LEGB is Python's name lookup order: Local, Enclosing, Global, and Built-in. When Python
sees a name, it searches these scopes in that order.

Question:

What is lexical scope?

Model Answer:

Lexical scope means a function resolves names based on where it is defined, not where it is called.

## Intermediate Questions

Question:

Why does `count = count + 1` raise `UnboundLocalError` inside a function?

Model Answer:

Because Python sees an assignment to `count` in the function and treats it as a local
variable. Then the function tries to read the local variable before it has a value.

Question:

What is the difference between `global` and `nonlocal`?

Model Answer:

`global` binds a name in module global scope. `nonlocal` binds a name in the nearest
enclosing function scope.

## Senior Questions

Question:

How would you define closure in engineering terms?

Model Answer:

A closure is a function object plus a captured environment. The function can keep access
to variables from the scope where it was defined, even after the outer function has returned.

Question:

Why is late binding a common source of bugs?

Model Answer:

Late binding means closures look up variables when the function is called, not when it is
created. If functions are created inside a loop, they may all refer to the same final loop variable.

Question:

How does scope affect backend systems?

Model Answer:

Scope controls where state comes from. Hidden global state can leak request data in FastAPI,
mix browser jobs in Playwright, and pollute AI conversation state. Production code should
make state ownership explicit.

---

# Today's Takeaway

Today's core idea:

```text
Python looks up names by LEGB.
Functions use lexical scope.
Closures preserve captured environments.
Mutation changes objects; rebinding changes names.
```

Production rule:

```text
Avoid hidden state.
Make scope and ownership explicit.
```

This explains why global request state, global Playwright pages, and global AI message
history are dangerous.

---

# Before Next Lesson Checklist

Students should confirm they can answer these questions without looking at the notes.

- [ ] What does LEGB mean?
- [ ] What is lexical scope?
- [ ] Why does Python not use dynamic scope?
- [ ] Why does `count = count + 1` raise `UnboundLocalError`?
- [ ] When does `global` work?
- [ ] Why should global request state be avoided in FastAPI?
- [ ] What does `nonlocal` do?
- [ ] Why does `append()` not require `global` or `nonlocal`?
- [ ] What is a closure in engineering terms?
- [ ] Why does `make_counter()` keep returning `1`, `2`, `3`?
- [ ] What is late binding?
- [ ] Why does `def f(i=i)` fix the late binding loop problem?

---

# Best Practices

* Prefer explicit parameters over hidden global dependencies.
* Use global variables for constants, not request state.
* Use `nonlocal` only when closure state is intentional.
* Name mutating functions clearly.
* Avoid global Playwright `Page` objects.
* Scope FastAPI dependencies to the request lifecycle.
* Scope AI conversation state by user and session.
* Use closures for stable configuration, not hidden mutable state.

---

# Common Bugs

## Bug 1: Accidental Local Variable

```python
count = 0


def add():
    count = count + 1
```

Why it happens:

Python treats `count` as local because of assignment.

## Bug 2: Global Request State

```python
current_user = None
```

Why it happens:

The developer wants convenient access but accidentally creates shared process state.

## Bug 3: Misusing `nonlocal`

```python
def outer():
    state = []

    def inner():
        nonlocal state
        state.append(1)
```

Why it happens:

The code uses `nonlocal` even though `append()` mutates the list and does not require rebinding.

## Bug 4: Late Binding in Loops

```python
funcs = []

for i in range(3):
    def f():
        return i

    funcs.append(f)
```

Why it happens:

All functions share the same loop variable.

---

# Code Examples

## Simple

```python
value = "global"


def show() -> str:
    return value
```

## Real Backend Function

```python
def build_cache_key(user_id: str, resource: str) -> tuple[str, str]:
    return user_id, resource
```

## FastAPI

```python
def get_current_user_id() -> str:
    return "user-123"
```

## Playwright

```python
async def use_page(page, url: str) -> None:
    await page.goto(url)
```

## AI Backend

```python
def make_prompt_builder(system_prompt: str):
    def build(user_input: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

    return build
```

---

# Homework

## Mini Exercises

1. Predict LEGB output for three nested function examples.
2. Explain `UnboundLocalError` using compile-time local variable determination.
3. Rewrite one `global` example using explicit parameters.
4. Build `make_counter()` and explain why the count survives.
5. Reproduce the late binding bug and fix it with `i=i`.
6. Write one FastAPI global request state bug.
7. Write one Playwright global page bug.
8. Write one AI prompt builder closure.

## Repository Task

After completing this lesson, synchronize:

* `docs/python/day04-scope-legb.md`
* `cheat_sheets/python.md`
* `interview/python.md`
* `PROJECT_STATUS.md`
* `TASKS.md`
* `CHANGELOG.md`
