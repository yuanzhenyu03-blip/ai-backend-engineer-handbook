# Lesson 5 — Closures

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day04 — Scope & LEGB

Next Lesson: Day06 — Decorators

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Define closure as function object plus captured environment.
* Explain why an inner function can access variables after the outer function returns.
* Explain captured environment and state preservation.
* Explain why `nonlocal` is needed for rebinding closure state.
* Explain why `x = x + 1` can raise `UnboundLocalError`.
* Explain why the error is not `NameError`.
* Explain factory functions as configuration and business logic separation.
* Compare closure and class design.
* Explain late binding and the `i=i` default argument fix.
* Connect closures to FastAPI dependency factories, Playwright configuration factories,
  and AI backend prompt builders.

---

# Why This Matters

Closures are where Python functions become configurable engineering tools.

In Day01, we learned that functions are objects.

In Day04, we learned lexical scope and LEGB.

Today we combine both ideas:

```text
Closure = Function Object + Captured Environment
```

That definition is the core of the lesson.

A closure is not simply "a function inside another function."

The important engineering idea is that a returned function can preserve access to variables
from the scope where it was created.

That explains why this works:

```python
counter = make_counter()

counter()
counter()
counter()
```

The outer function already returned, but the returned function still remembers its captured
environment.

This matters in backend work because closures are used to build:

* FastAPI dependency factories
* configured validators
* Playwright job factories
* retry policies
* prompt builders
* LLM tool wrappers
* callbacks
* decorators

The production question is not "can I write a nested function?"

The question is:

```text
What state does this function capture, and who owns that state?
```

---

# Roadmap Position

Day05 sits directly after Scope & LEGB because closures depend on lexical scope.

```text
Day01: Function Objects
        |
        v
Day04: Scope & LEGB
        |
        v
Day05: Closures
        |
        v
Day06: Decorators
        |
        v
FastAPI / Playwright / AI Backend Factories
```

Decorators will be much easier after Day05.

A decorator is often a function that takes a function, creates an inner function, captures
something, and returns a new function.

So Day05 is not optional theory. It is the foundation for production Python patterns.

---

# Lesson Map

Today's Lesson

1. Closure Definition
2. Function Object + Captured Environment
3. State Preservation
4. `nonlocal`
5. `UnboundLocalError`
6. Factory Function
7. Closure vs Class
8. Late Binding
9. FastAPI Dependency Factory
10. Playwright Configuration Factory
11. AI Prompt Builder
12. Interview Review
13. Today's Takeaway

---

# Estimated Study Time

Reading: 90-120 minutes

Exercises: 60-90 minutes

Coding: 60-90 minutes

Review: 30-45 minutes

Total: 4.5-5.5 hours

---

# Main Concepts

## Closure

Classroom definition:

```text
Closure = Function Object + Captured Environment
```

Do not define closure as:

```text
A function inside another function.
```

That is incomplete.

A nested function becomes a closure when it captures variables from an outer scope and can
use them later.

Example:

```python
def outer():
    message = "hello"

    def inner():
        return message

    return inner
```

Use it:

```python
func = outer()
print(func())
```

Output:

```text
hello
```

`outer()` already returned.

So why can `inner()` still use `message`?

Because `inner` is a function object with a captured environment.

Memory model:

```text
outer() call frame:

message -> "hello"

return inner
        |
        v
function object: inner
        |
        v
captured environment:
message -> "hello"
```

The call frame is gone, but the captured environment stays alive because the returned
function object still needs it.

## Captured Environment

The captured environment is the set of variables from an enclosing scope that a function
keeps access to.

Think of it like this:

```text
Function Object
      |
      v
Code + Captured Variables
```

The function has code.

The captured environment gives the code access to variables that were available when the
function was defined.

This is possible because Python uses lexical scope.

The function remembers where it was defined, not where it is called.

## State Preservation

Closures can preserve state.

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

Why?

```text
counter function object
        |
        v
captured environment:
count -> 0
count -> 1
count -> 2
count -> 3
```

The same captured `count` is preserved between calls.

This is state preservation.

Tech Lead question:

Is this good or dangerous?

Answer:

It depends on ownership.

If the closure state belongs to one counter, it is fine.

If the closure state accidentally stores shared user request state, it is dangerous.

## `nonlocal`

`nonlocal` is needed when an inner function wants to rebind a variable from the nearest
enclosing scope.

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

`count += 1` is rebinding.

For integers:

```text
count += 1
```

means:

```text
count = count + 1
```

The inner function needs to tell Python:

```text
Do not create a new local count.
Use the count from the nearest enclosing scope.
```

That is what `nonlocal count` does.

## Why `x = x + 1` Raises `UnboundLocalError`

Consider:

```python
def outer():
    x = 0

    def inner():
        x = x + 1
        return x

    return inner
```

This raises:

```text
UnboundLocalError
```

Why not `NameError`?

Because Python can see that `x` exists as a name in the local scope of `inner`.

It decides this at compile time because `inner()` assigns to `x`.

So Python treats `x` as local inside `inner()`.

Then this happens:

```text
local x = local x + 1
```

But local `x` has not been assigned yet.

That is why the error is:

```text
UnboundLocalError
```

not:

```text
NameError
```

`NameError` means Python cannot find the name.

`UnboundLocalError` means Python found the local name rule, but the local variable has no
value yet.

## Mutation Does Not Require `nonlocal`

Compare rebinding with mutation.

Rebinding:

```python
def outer():
    x = 0

    def inner():
        nonlocal x
        x = x + 1
```

Mutation:

```python
def outer():
    items = []

    def inner():
        items.append(1)
```

`items.append(1)` does not rebind `items`.

It mutates the list object.

Diagram:

```text
Rebinding:

x -> 0

x = x + 1

x -> 1

Mutation:

items -> []

items.append(1)

items -> [1]
```

That is why `append()` does not require `nonlocal`.

But it can still be dangerous if the list is shared state.

## Factory Function

A factory function is a function that creates and returns another configured object or
function.

Closure-based factory:

```python
def make_multiplier(factor: int):
    def multiply(value: int) -> int:
        return value * factor

    return multiply
```

Use it:

```python
double = make_multiplier(2)
triple = make_multiplier(3)

print(double(10))
print(triple(10))
```

Output:

```text
20
30
```

Why does this work?

Each returned function captures its own `factor`.

```text
double -> function + factor: 2
triple -> function + factor: 3
```

Factory functions separate configuration from business logic.

Configuration:

```text
factor = 2
```

Business logic:

```text
value * factor
```

This is why factory functions appear in FastAPI dependencies, Playwright job builders,
and AI prompt builders.

## Closure vs Class

Both closures and classes can preserve state.

Closure:

```python
def make_multiplier(factor: int):
    def multiply(value: int) -> int:
        return value * factor

    return multiply
```

Class:

```python
class Multiplier:
    def __init__(self, factor: int) -> None:
        self.factor = factor

    def __call__(self, value: int) -> int:
        return value * self.factor
```

Use closure when:

* state is small
* behavior is simple
* you want a lightweight configured function

Use class when:

* state is complex
* multiple methods are needed
* lifecycle is important
* behavior needs explicit structure

Interview answer:

```text
A closure is lighter.
A class is more explicit and scalable.
```

## Late Binding

Late binding means closures look up variables when the function is called, not when it is
created.

Classic bug:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

Use it:

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

Closures capture the variable `i`, not the value of `i` at each loop iteration.

All functions share the same `i`.

After the loop ends:

```text
i -> 2
```

Diagram:

```text
f0 ----+
      |
f1 ----+--> captured variable i -> 2
      |
f2 ----+
```

## Early Binding with Default Arguments

Fix:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f(i=i):
            return i

        funcs.append(f)

    return funcs
```

Output:

```text
0
1
2
```

Why?

Default arguments are evaluated when the function is defined.

So each function stores its own current value of `i`.

This is early binding through default arguments.

---

# Engineering Thinking

## Think First: What Is Being Captured?

Before using a closure, ask:

```text
What variables are captured?
Are they immutable configuration values?
Are they mutable state?
Who owns that state?
How long will this closure live?
```

Closures are powerful because they preserve context.

Closures are risky because preserved context can become hidden state.

## Why Factory Functions Matter

Factory functions help separate configuration from business logic.

Example:

```text
configure once -> reuse many times
```

This is valuable in backend systems:

* create dependency functions
* build prompt builders
* configure retry policies
* generate Playwright job functions
* build validation logic

The Tech Lead question is:

```text
Is this closure making the code clearer, or hiding state?
```

## Production Risks

Common risks:

* hidden mutable state
* late binding bugs
* accidental shared counters
* request state captured beyond request lifetime
* Playwright page objects captured too long
* AI conversation history shared across users

## Tech Lead Review

A senior engineer would review:

* What does the closure capture?
* Is captured state immutable or mutable?
* Does the closure outlive a request or job?
* Would a class make ownership clearer?
* Is `nonlocal` necessary?
* Could late binding affect callbacks?

---

# Classroom Exercises

## Exercise 1: Is This a Closure?

Question:

Is this a closure?

```python
def outer():
    x = 10

    def inner():
        return x

    return inner
```

Think First:

Does the returned function capture something from the outer scope?

Expected Output:

```text
Yes
```

Explanation:

`inner` is a function object that captures `x` from `outer()`.

Follow-up Question:

What is the captured environment?

## Exercise 2: Output Prediction

Question:

What prints?

```python
def outer():
    message = "hello"

    def inner():
        return message

    return inner


func = outer()
print(func())
```

Think First:

Has `outer()` already returned when `func()` runs?

Expected Output:

```text
hello
```

Explanation:

The returned function preserves the captured environment.

Follow-up Question:

Why is this not a `NameError`?

## Exercise 3: Closure Memory

Question:

Draw the memory model for:

```python
counter = make_counter()
```

Starter Code:

```python
def make_counter():
    count = 0

    def counter():
        nonlocal count
        count += 1
        return count

    return counter
```

Think First:

Where does `count` live after `make_counter()` returns?

Expected Output:

```text
counter -> function object + captured count
```

Explanation:

The call frame returns, but the captured environment remains alive.

Follow-up Question:

What would happen if nobody kept a reference to `counter`?

## Exercise 4: `nonlocal`

Question:

What prints?

```python
counter = make_counter()

print(counter())
print(counter())
```

Think First:

Does `count += 1` mutate or rebind?

Expected Output:

```text
1
2
```

Explanation:

`count += 1` rebinds `count`, so `nonlocal count` is required.

Follow-up Question:

Why does `items.append(1)` not require `nonlocal`?

## Exercise 5: Factory Function

Question:

Implement `make_multiplier`.

Starter Code:

```python
def make_multiplier(factor: int):
    ...
```

Think First:

What should the inner function capture?

Expected Output:

```text
make_multiplier(2)(10) -> 20
make_multiplier(3)(10) -> 30
```

Explanation:

Each returned function captures its own `factor`.

Follow-up Question:

When would a class be better?

## Exercise 6: Fix `UnboundLocalError`

Question:

Fix this code:

```python
def outer():
    x = 0

    def inner():
        x = x + 1
        return x

    return inner
```

Think First:

Is `x = x + 1` mutation or rebinding?

Expected Output:

```python
def outer():
    x = 0

    def inner():
        nonlocal x
        x = x + 1
        return x

    return inner
```

Explanation:

`nonlocal x` tells Python to rebind `x` in the nearest enclosing scope.

Follow-up Question:

Why is the error `UnboundLocalError` rather than `NameError`?

## Exercise 7: Late Binding

Question:

What prints?

```python
funcs = make_funcs()

print(funcs[0]())
print(funcs[1]())
print(funcs[2]())
```

Starter Code:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

Think First:

Does the closure capture the variable or the value?

Expected Output:

```text
2
2
2
```

Explanation:

The closure captures the variable `i`, and after the loop finishes `i` is `2`.

Follow-up Question:

How do you fix it?

## Exercise 8: Fix Late Binding

Question:

Fix the loop with default arguments.

Expected Output:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f(i=i):
            return i

        funcs.append(f)

    return funcs
```

Explanation:

`i=i` stores the current value as a default argument when the function is defined.

Follow-up Question:

Why is this early binding?

## Exercise 9: FastAPI Dependency Factory

Question:

Build a dependency factory that captures a role.

Starter Code:

```python
def require_role(role: str):
    ...
```

Expected Output:

```python
def require_role(role: str):
    def dependency() -> str:
        return role

    return dependency
```

Explanation:

The dependency captures configuration and can be passed to `Depends()`.

Follow-up Question:

What should this dependency not capture?

## Exercise 10: Playwright Timeout Factory

Question:

Create a function that captures a timeout and applies it to a page action.

Expected Output:

```python
def make_click(timeout_ms: int):
    async def click(locator):
        await locator.click(timeout=timeout_ms)

    return click
```

Explanation:

The closure captures stable configuration, not a global page object.

Follow-up Question:

Why should the `Page` object usually not be captured globally?

## Exercise 11: AI Prompt Builder Factory

Question:

Create a prompt builder that captures a system prompt.

Expected Output:

```python
def make_prompt_builder(system_prompt: str):
    def build(user_input: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

    return build
```

Explanation:

The system prompt is stable configuration. The user input stays explicit.

Follow-up Question:

Why should shared conversation history not be captured here?

---

# FastAPI Connections

FastAPI often uses factory functions to create dependencies.

Example:

```python
from fastapi import Depends, FastAPI

app = FastAPI()


def require_role(role: str):
    def dependency() -> str:
        return role

    return dependency


@app.get("/admin")
def read_admin(role: str = Depends(require_role("admin"))) -> dict[str, str]:
    return {"required_role": role}
```

This is a dependency factory.

`require_role("admin")` creates a configured dependency function.

Engineering benefit:

```text
configuration: "admin"
business logic: dependency execution
```

Production warning:

Do not capture request-specific mutable state in a closure that may live beyond one request.

Good closure state:

* role name
* static configuration
* feature flag name

Dangerous closure state:

* current user object
* request body
* database session with unclear lifecycle
* mutable list of request data

---

# Playwright Connections

Playwright configuration factories can be useful.

Example:

```python
def make_wait_and_click(timeout_ms: int):
    async def click(locator):
        await locator.click(timeout=timeout_ms)

    return click
```

This captures stable configuration.

It does not capture the `Page` object.

Why avoid capturing `Page` globally?

`Page` is live mutable browser state.

If a closure captures a page and is reused across jobs, jobs can interfere with each other.

Better pattern:

```python
def make_login(email: str, password: str):
    async def login(page) -> None:
        await page.fill("#email", email)
        await page.fill("#password", password)

    return login
```

Configuration is captured.

The page is passed explicitly.

Engineering rule:

```text
Capture stable configuration.
Pass lifecycle objects explicitly.
```

---

# AI Backend Connections

Closures are useful for AI prompt builders.

Example:

```python
def make_prompt_builder(system_prompt: str):
    def build(user_input: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

    return build
```

This captures a stable system prompt.

It keeps user input explicit.

This pattern is useful for:

* LLM factory functions
* dependency factories
* prompt builders
* tool wrappers
* callback builders

Production warning:

Do not capture shared mutable `messages` or `history` unless the closure is scoped to one
user session.

Bad pattern:

```python
def make_chat():
    messages = []

    def chat(user_input: str):
        messages.append({"role": "user", "content": user_input})
        return messages

    return chat
```

This can be safe only if each user gets a separate `chat` closure.

It is dangerous if one closure is shared across users.

---

# English Interview

## Key Vocabulary

* closure
* captured environment
* function object
* state preservation
* `nonlocal`
* factory function
* late binding
* early binding
* dependency factory
* prompt builder

## Beginner Questions

Question:

What is a closure?

Model Answer:

A closure is a function object plus a captured environment. It allows a function to keep
access to variables from the scope where it was created.

Question:

What is a captured environment?

Model Answer:

A captured environment is the set of outer-scope variables that a function keeps access to.

Question:

Why can an inner function access variables after the outer function returns?

Model Answer:

Because the returned function object keeps its captured environment alive.

Question:

What does `nonlocal` do?

Model Answer:

`nonlocal` allows an inner function to rebind a variable from the nearest enclosing scope.

## Intermediate Questions

Question:

Explain closure vs class.

Model Answer:

A closure is lightweight and useful for simple captured configuration. A class is more
explicit and better when state is complex or multiple methods are needed.

Question:

What is a factory function?

Model Answer:

A factory function creates and returns a configured function or object.

Question:

Why is closure useful in backend development?

Model Answer:

Closures help separate configuration from business logic. They are useful for dependency
factories, prompt builders, callbacks, and configured automation jobs.

Question:

Explain late binding.

Model Answer:

Late binding means a closure looks up a captured variable when the function is called,
not when it is created.

## Senior Questions

Question:

Explain Python closure from the perspective of function objects.

Model Answer:

A Python closure is a function object that carries references to variables from its lexical
environment. The function object can be called later, and it still has access to those
captured variables.

Question:

Why does Python capture names instead of values?

Model Answer:

Python closures capture variables from the lexical environment. This allows state preservation,
but it also creates late binding behavior. If the variable changes before the closure is called,
the closure observes the current value.

Question:

Explain dependency factory in FastAPI.

Model Answer:

A dependency factory is a function that returns a configured dependency function. The outer
function captures configuration, while the inner dependency is called by FastAPI.

Question:

Explain prompt factory in AI Backend.

Model Answer:

A prompt factory returns a configured prompt builder. It can capture stable configuration
such as a system prompt while keeping user input explicit.

Question:

Explain trade-offs between closure and OOP.

Model Answer:

Closures are concise and good for simple captured configuration. Classes are more explicit,
easier to extend, and better for complex state, lifecycle, or multiple behaviors.

---

# Today's Takeaway

Today's core idea:

```text
Closure = Function Object + Captured Environment
```

Closures preserve state.

That makes them powerful for factory functions.

It also makes them risky when they capture mutable state accidentally.

Production rule:

```text
Capture stable configuration.
Avoid hidden shared mutable state.
Pass lifecycle objects explicitly.
```

This is the bridge to decorators, dependency factories, Playwright automation factories,
and AI prompt builders.

---

# Before Next Lesson Checklist

Students should confirm they can answer these questions without looking at the notes.

- [ ] What is the engineering definition of closure?
- [ ] What is a captured environment?
- [ ] Why can a function access local variables after the outer function returns?
- [ ] Why does `nonlocal` exist?
- [ ] Why does `x = x + 1` raise `UnboundLocalError`?
- [ ] Why is that not `NameError`?
- [ ] What is a factory function?
- [ ] When should you use a closure instead of a class?
- [ ] When should you use a class instead of a closure?
- [ ] Why does the late binding example print `2`, `2`, `2`?
- [ ] How does `i=i` fix late binding?
- [ ] How can closures support FastAPI dependency factories?
- [ ] How can closures support Playwright configuration factories?
- [ ] How can closures support AI prompt builders?

---

# Best Practice

* Use closures for small, focused configuration.
* Use classes when state or behavior becomes complex.
* Use `nonlocal` only when rebinding closure state is intentional.
* Avoid capturing request-specific mutable state.
* Avoid capturing Playwright lifecycle objects globally.
* Avoid sharing AI conversation history across users.
* Fix late binding with default arguments or a separate factory function.
* Make captured state obvious in function names and code review.

---

# Common Bugs

## Bug 1: Defining Closure Too Loosely

Mistake:

```text
Closure means a function inside another function.
```

Why it is wrong:

The important part is captured environment.

## Bug 2: Missing `nonlocal`

```python
def outer():
    x = 0

    def inner():
        x = x + 1
```

Why it happens:

Python treats `x` as local inside `inner()`.

## Bug 3: Late Binding

```python
for i in range(3):
    def f():
        return i
```

Why it happens:

The closure captures the variable `i`, not the value at that moment.

## Bug 4: Capturing Shared Mutable State

```python
messages = []
```

Why it happens:

The closure accidentally shares state across users or jobs.

---

# Code Examples

## Simple Closure

```python
def outer():
    value = "hello"

    def inner():
        return value

    return inner
```

## Factory Function

```python
def make_multiplier(factor: int):
    def multiply(value: int) -> int:
        return value * factor

    return multiply
```

## FastAPI Dependency Factory

```python
def require_role(role: str):
    def dependency() -> str:
        return role

    return dependency
```

## Playwright Timeout Factory

```python
def make_click(timeout_ms: int):
    async def click(locator):
        await locator.click(timeout=timeout_ms)

    return click
```

## AI Prompt Builder

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

1. Identify whether a function is a closure.
2. Predict closure output.
3. Draw the captured environment memory model.
4. Explain why `nonlocal` is needed in `make_counter()`.
5. Implement `make_multiplier`.
6. Implement a closure-based counter.
7. Rewrite a closure as a class.
8. Predict late binding output.
9. Fix late binding with `i=i`.
10. Build a FastAPI dependency factory.
11. Build a Playwright timeout factory.
12. Build an AI prompt builder factory.

## Repository Task

After completing this lesson, synchronize:

* `docs/python/day05-closures.md`
* `cheat_sheets/python.md`
* `interview/python.md`
* `PROJECT_STATUS.md`
* `TASKS.md`
* `CHANGELOG.md`
