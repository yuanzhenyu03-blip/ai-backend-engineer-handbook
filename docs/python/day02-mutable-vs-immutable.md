# Lesson 2 — Mutable vs Immutable

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day01 — Python Object Model

Next Lesson: Day03 — Functions & Parameter Passing

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain the difference between mutable and immutable objects.
* Explain why `b = a` copies a reference, not the object.
* Use `id()` to verify object identity.
* Explain why `append()` mutates a list in place.
* Explain why `a = a + [3]` creates a new list.
* Explain why `a += [3]` mutates a list in place.
* Explain shallow copy and deep copy.
* Explain why `list`, `dict`, and `set` cannot be dictionary keys.
* Explain why a tuple can be a key only when all nested values are hashable.
* Connect mutable state bugs to FastAPI, Playwright, and AI backend systems.

---

# Why This Matters

Mutable vs immutable is not only a Python detail.

It is the first serious lesson about state ownership.

In Day01, we learned this mental model:

```text
name -> reference -> object
```

Today we ask the next engineering question:

```text
Can the object behind the reference change?
```

That question matters because backend systems move data through many layers:

```text
Request
  |
  v
Validation
  |
  v
Business logic
  |
  v
Database / Browser / AI Model
  |
  v
Response
```

If one layer accidentally mutates data owned by another layer, bugs become difficult to find. The code may look harmless, but one shared list, dictionary, browser context, cookie jar, or message history can leak state across users or jobs.

This is why production engineers care about mutability:

* FastAPI services must avoid request data leaking between users.
* Playwright workers must avoid shared page, context, cookie, or header objects.
* AI backend systems must avoid shared `messages`, `history`, or `state` objects across users.

The classroom goal today is simple:

```text
Before changing an object, ask who else can see this object.
```

---

# Roadmap Position

Day02 builds directly on Day01.

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
FastAPI / Playwright / AI Backend State Management
```

Day01 explained that names point to objects.

Day02 explains what happens when those objects can change.

Day03 will use both ideas to explain how arguments are passed into functions.

This is the foundation for future topics such as:

* dependency injection
* request lifecycle
* browser context isolation
* AI conversation memory
* safe function design
* production debugging

---

# Lesson Map

Today's Lesson

1. Mutable vs Immutable
2. Reference Assignment
3. `id()` Experiments
4. In-place Mutation with `append()`
5. `a = a + [...]` vs `a += [...]`
6. Shallow Copy
7. Deep Copy
8. Hashable vs Unhashable
9. FastAPI Connections
10. Playwright Connections
11. AI Backend Connections
12. Interview Review
13. Today's Takeaway

---

# Estimated Study Time

Reading: 80-110 minutes

Exercises: 60-90 minutes

Coding: 45-60 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Main Concepts

## Mutable vs Immutable

An object is mutable if its value can change after the object is created.

Examples:

* `list`
* `dict`
* `set`

An object is immutable if its value cannot change after the object is created.

Examples:

* `int`
* `float`
* `str`
* `bool`
* `tuple`, if all nested values are immutable

The key question is not whether a variable changes.

The key question is whether the object changes.

```python
name = "python"
name = "fastapi"
```

This does not mutate the original string.

It rebinds the name `name` to a different string object.

```text
Before:

name -> "python"

After:

name -> "fastapi"

"python" still exists until Python can clean it up.
```

Now compare a list:

```python
items = ["python"]
items.append("fastapi")
```

This mutates the same list object.

```text
Before:

items -> ["python"]

After:

items -> ["python", "fastapi"]

Same object. Changed value.
```

Why does this design exist?

Mutable objects are efficient for containers that need to grow or change. A list should not need to create a brand-new object every time we append one item.

The trade-off is that shared mutable objects can create hidden side effects.

## Reference Assignment: `b = a`

Assignment does not copy the object.

It binds another name to the same object.

```python
a = [1, 2]
b = a

b.append(3)

print(a)
print(b)
```

Output:

```text
[1, 2, 3]
[1, 2, 3]
```

Memory model:

```text
a ----+
     |
     v
b -> list object: [1, 2, 3]
```

This is one of the most important backend debugging ideas in Python.

If two names point to the same mutable object, mutation through one name is visible through the other.

## `id()` Verifies Object Identity

`id()` shows the identity of an object during its lifetime.

It helps us test whether two names point to the same object.

```python
a = [1, 2]
b = a

print(id(a))
print(id(b))
print(a is b)
```

Expected result:

```text
same id
same id
True
```

Use `id()` as a learning and debugging tool.

In production code, we usually design clear ownership instead of relying on printed object IDs.

## `append()` Mutates a List In Place

`append()` changes the list object itself.

```python
a = [1, 2]
before = id(a)

a.append(3)
after = id(a)

print(a)
print(before == after)
```

Expected result:

```text
[1, 2, 3]
True
```

Diagram:

```text
Before:

a -> list object #1: [1, 2]

After append:

a -> list object #1: [1, 2, 3]
```

The name still points to the same object.

The object changed internally.

## `a = a + [3]` Creates a New List

The expression `a + [3]` creates a new list.

Then assignment binds `a` to that new list.

```python
a = [1, 2]
before = id(a)

a = a + [3]
after = id(a)

print(a)
print(before == after)
```

Expected result:

```text
[1, 2, 3]
False
```

Diagram:

```text
Before:

a -> list object #1: [1, 2]

After:

a -> list object #2: [1, 2, 3]

list object #1 is no longer bound to a
```

This matters when another name still points to the original list.

```python
a = [1, 2]
b = a

a = a + [3]

print(a)
print(b)
```

Output:

```text
[1, 2, 3]
[1, 2]
```

Diagram:

```text
a -> list object #2: [1, 2, 3]

b -> list object #1: [1, 2]
```

## `a += [3]` Mutates a List In Place

For lists, `+=` usually performs in-place extension.

```python
a = [1, 2]
b = a
before = id(a)

a += [3]
after = id(a)

print(a)
print(b)
print(before == after)
```

Expected result:

```text
[1, 2, 3]
[1, 2, 3]
True
```

Diagram:

```text
a ----+
     |
     v
b -> list object #1: [1, 2, 3]
```

Important classroom rule:

```text
a = a + [3] creates a new list.
a += [3] mutates the existing list.
```

For immutable objects such as integers and strings, `+=` cannot mutate the original object. It creates a new object and rebinds the name.

## Shallow Copy

`copy.copy()` copies only the first level.

Nested mutable objects are still shared.

```python
import copy

original = [["python"], ["fastapi"]]
cloned = copy.copy(original)

cloned[0].append("playwright")

print(original)
print(cloned)
```

Output:

```text
[['python', 'playwright'], ['fastapi']]
[['python', 'playwright'], ['fastapi']]
```

Memory model:

```text
original -> outer list #1
              |
              +--> inner list A: ["python", "playwright"]
              +--> inner list B: ["fastapi"]

cloned   -> outer list #2
              |
              +--> inner list A: ["python", "playwright"]
              +--> inner list B: ["fastapi"]
```

The outer list is copied.

The inner lists are shared.

Shallow copy is useful when the first layer should be independent but nested objects are intentionally shared.

It is dangerous when the engineer assumes everything was copied.

## Deep Copy

`copy.deepcopy()` recursively copies the object tree.

```python
import copy

original = [["python"], ["fastapi"]]
cloned = copy.deepcopy(original)

cloned[0].append("playwright")

print(original)
print(cloned)
```

Output:

```text
[['python'], ['fastapi']]
[['python', 'playwright'], ['fastapi']]
```

Memory model:

```text
original -> outer list #1
              |
              +--> inner list A1: ["python"]
              +--> inner list B1: ["fastapi"]

cloned   -> outer list #2
              |
              +--> inner list A2: ["python", "playwright"]
              +--> inner list B2: ["fastapi"]
```

Deep copy is safer when full isolation is required.

The trade-off is cost.

For large data structures, deep copy can be expensive in memory and time.

Production engineers should not blindly deep copy everything. They should decide ownership clearly.

## Hashable vs Unhashable

A hashable object can be used as a dictionary key.

Dictionary keys must be stable because Python uses the key's hash to find the stored value.

Mutable objects such as `list`, `dict`, and `set` are unhashable.

```python
cache = {}

cache[[1, 2]] = "value"
```

This raises:

```text
TypeError: unhashable type: 'list'
```

Why?

If a list could be a key, this would be unsafe:

```python
key = [1, 2]
cache[key] = "value"
key.append(3)
```

The key's value changed after insertion. The dictionary would not be able to rely on a stable hash.

Immutable objects such as strings, integers, and many tuples are hashable:

```python
cache = {}
cache[("user", 123)] = "active"
```

But a tuple is hashable only if everything inside it is hashable.

```python
valid_key = ("user", 123)
invalid_key = ("user", [1, 2])

cache = {}
cache[valid_key] = "ok"
cache[invalid_key] = "fail"
```

The second key fails because the tuple contains a list.

Rule:

```text
Hashable means stable enough to be used as a dictionary key.
Immutable outer container is not enough.
Nested values must also be hashable.
```

---

# Engineering Thinking

## The Real Question: Who Owns This Object?

When an engineer sees a mutable object, they should ask:

```text
Who owns this object?
Who is allowed to mutate it?
Who else can see it?
Should I copy it before changing it?
```

This is more important than memorizing which method changes `id()`.

In production, bugs often appear when ownership is unclear:

* A helper mutates the caller's payload.
* A global list accumulates request data.
* A Playwright context is reused across unrelated jobs.
* An AI chat history list is shared between users.

## Design Trade-offs

Mutable objects are useful because they are efficient and convenient.

Immutable objects are useful because they are safer to share.

Copying creates isolation.

Deep copying creates stronger isolation but costs more.

The engineering decision is not "mutable bad, immutable good."

The real decision is:

```text
What level of sharing is safe for this system?
```

## Tech Lead Questions

Question:

If a function receives a list and calls `append()`, what should a reviewer ask?

Think first.

Expected student answer:

The reviewer should ask whether the function is allowed to mutate caller-owned data.

Explanation:

Mutation may be correct, but it must be intentional. If the function name and documentation do not make mutation clear, future engineers may misunderstand its behavior.

Question:

Should we use `deepcopy()` everywhere to avoid bugs?

Expected student answer:

No. Deep copy can be expensive and may hide unclear ownership. It should be used when full isolation is required.

Explanation:

Better engineering is to design ownership boundaries clearly.

---

# Classroom Exercises

## Exercise 1: Reference Assignment

Question:

What prints?

```python
a = [1, 2]
b = a
b.append(3)

print(a)
print(a is b)
```

Think first.

Expected student answer:

```text
[1, 2, 3]
True
```

Explanation:

`b = a` binds `b` to the same list object. `append()` mutates that list in place.

## Exercise 2: `a = a + [3]`

Question:

What prints?

```python
a = [1, 2]
b = a
a = a + [3]

print(a)
print(b)
print(a is b)
```

Expected student answer:

```text
[1, 2, 3]
[1, 2]
False
```

Explanation:

`a + [3]` creates a new list. The name `a` is rebound to the new list. `b` still points to the old list.

## Exercise 3: `a += [3]`

Question:

What prints?

```python
a = [1, 2]
b = a
a += [3]

print(a)
print(b)
print(a is b)
```

Expected student answer:

```text
[1, 2, 3]
[1, 2, 3]
True
```

Explanation:

For a list, `+=` mutates the existing object in place.

## Exercise 4: Shallow Copy

Question:

What happens to `original`?

```python
import copy

original = [{"tags": ["python"]}]
cloned = copy.copy(original)

cloned[0]["tags"].append("fastapi")

print(original)
```

Expected student answer:

```text
[{'tags': ['python', 'fastapi']}]
```

Explanation:

The outer list was copied, but the inner dictionary and inner list were still shared.

## Exercise 5: Hashable Tuple

Question:

Which one can be used as a dictionary key?

```python
key_a = ("user", 1)
key_b = ("user", [1, 2])
```

Expected student answer:

`key_a` can be used as a key. `key_b` cannot.

Explanation:

`key_b` contains a list. A tuple is hashable only when all nested values are hashable.

---

# FastAPI Connections

FastAPI applications must avoid shared mutable state between requests.

Bad example:

```python
from fastapi import FastAPI

app = FastAPI()
messages: list[str] = []


@app.post("/messages")
def add_message(message: str) -> dict[str, list[str]]:
    messages.append(message)
    return {"messages": messages}
```

Problem:

`messages` is global mutable state. Every request shares the same list.

Risk:

One user's data can appear in another user's response.

Better design:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class MessageRequest(BaseModel):
    message: str


@app.post("/messages")
def add_message(payload: MessageRequest) -> dict[str, str]:
    return {"message": payload.message}
```

For real persistence, store messages in a database with clear user ownership.

Engineering rule:

```text
Request-specific state should be request-scoped.
Shared state belongs in a database, cache, or explicitly managed service.
```

This lesson explains why mutable globals are risky.

---

# Playwright Connections

Playwright automation deals with live mutable external state:

* browser
* context
* page
* cookies
* headers
* storage state

Bad example:

```python
shared_headers = {"Authorization": "Bearer token-a"}


async def run_job(page, token: str) -> None:
    shared_headers["Authorization"] = f"Bearer {token}"
    await page.set_extra_http_headers(shared_headers)
    await page.goto("https://example.com/dashboard")
```

Problem:

`shared_headers` is a mutable dictionary shared across jobs.

If jobs run concurrently, one job can overwrite another job's token.

Better design:

```python
async def run_job(context, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    page = await context.new_page()
    await page.set_extra_http_headers(headers)
    await page.goto("https://example.com/dashboard")
```

Even better, create an isolated browser context per job when cookies or storage state matter.

Engineering rule:

```text
Do not share page, context, cookies, headers, or storage state across unrelated automation jobs.
```

This prevents task mix-ups, cookie leakage, and memory leaks.

---

# AI Backend Connections

AI backend systems often store conversation state:

* `messages`
* `history`
* `tools`
* `memory`
* `session_state`

Bad example:

```python
messages: list[dict[str, str]] = []


def chat(user_input: str) -> list[dict[str, str]]:
    messages.append({"role": "user", "content": user_input})
    return messages
```

Problem:

All users share the same `messages` list.

Risk:

* prompt pollution
* conversation leakage
* user data exposure
* confusing model responses

Better design:

```python
def chat(user_input: str, history: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if history is None:
        history = []

    next_history = history + [{"role": "user", "content": user_input}]
    return next_history
```

This creates a new list for the next conversation state.

For production systems, conversation history should be scoped by user and session, usually in a database or cache.

Engineering rule:

```text
AI memory must have clear ownership.
Never let multiple users accidentally share mutable conversation state.
```

---

# English Interview

## Key Vocabulary

* mutable object
* immutable object
* object identity
* reference assignment
* in-place mutation
* shallow copy
* deep copy
* hashable
* shared state

## Example Answer: Mutable vs Immutable

In Python, a mutable object can be changed after it is created, while an immutable object cannot. Lists and dictionaries are mutable. Strings, integers, and tuples are usually immutable. This matters in backend systems because shared mutable objects can leak state between requests or jobs.

## Example Answer: Shallow Copy vs Deep Copy

A shallow copy creates a new outer object, but nested objects may still be shared. A deep copy recursively copies the object tree. Deep copy gives stronger isolation, but it can be more expensive.

## Example Answer: Hashable

An object is hashable if it has a stable hash value and can be used as a dictionary key. Lists, dictionaries, and sets are not hashable because they are mutable. A tuple can be hashable only if all values inside it are also hashable.

---

# Today's Takeaway

Today's core idea:

```text
Assignment shares references.
Mutation changes objects.
Copying controls sharing.
Hashability requires stability.
```

The production lesson is:

```text
Before mutating data, understand ownership.
```

FastAPI, Playwright, and AI backend systems all depend on this idea because they all manage state across users, requests, jobs, or sessions.

---

# Before Next Lesson Checklist

Students should confirm they can answer these questions without looking at the notes.

- [ ] What is the difference between mutable and immutable objects?
- [ ] Why does `b = a` not copy a list?
- [ ] How can `id()` verify object identity?
- [ ] Why does `append()` keep the same list identity?
- [ ] Why does `a = a + [3]` create a new list?
- [ ] Why does `a += [3]` mutate a list in place?
- [ ] What does shallow copy copy?
- [ ] What does deep copy copy?
- [ ] Why are lists, dictionaries, and sets unhashable?
- [ ] Why can a tuple containing a list not be used as a dictionary key?
- [ ] How can shared mutable state break a FastAPI application?
- [ ] How can shared mutable state break a Playwright worker?
- [ ] How can shared mutable state pollute AI conversation history?
