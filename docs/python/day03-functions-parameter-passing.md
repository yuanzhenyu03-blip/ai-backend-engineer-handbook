# Lesson 3 — Functions & Parameter Passing

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day02 — Mutable vs Immutable

Next Lesson: Day04 — Scope & LEGB

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain how Python passes function arguments.
* Explain pass by object reference, also called call by sharing.
* Predict when a function call can mutate caller-visible data.
* Explain the difference between mutation and rebinding.
* Explain why `append()` affects the caller but `items = items + [...]` does not.
* Use `id()` to reason about function argument behavior.
* Connect parameter passing to FastAPI request handling, Playwright object lifecycles, and AI message state.
* Answer interview questions about Python's parameter passing model.

---

# Why This Matters

Function calls are where object references start moving through a real system.

In Day01, we learned:

```text
name -> reference -> object
```

In Day02, we learned:

```text
Some objects can be mutated.
Some objects cannot.
```

Today we put those two ideas inside a function call.

When a backend engineer writes this:

```python
def add_tag(tags: list[str]) -> None:
    tags.append("python")
```

the important question is not only "what does the function do?"

The deeper question is:

```text
Does this function change an object that the caller can still see?
```

This matters in production because most backend systems are built from functions:

* FastAPI route handlers are functions.
* FastAPI dependencies are functions or callables.
* Playwright automation jobs pass `page`, `context`, headers, and cookies into functions.
* AI backend systems pass `messages`, `history`, and `state` between layers.

If the team does not understand parameter passing, code review becomes weak.
A function may look harmless but mutate caller-owned state.
Another function may rebind a local name and the engineer may incorrectly expect the caller to change.

Today's core classroom idea:

```text
Python passes object references by value.
The function receives a new local name pointing to the same object.
```

That model is commonly called call by sharing.

---

# Roadmap Position

Day03 connects the first two Python design lessons to real function design.

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
FastAPI / Playwright / AI Backend Function Boundaries
```

Day03 is the bridge from object memory to function boundaries.

Day04 will ask where names are looked up.

Together, Day03 and Day04 explain why production Python code needs clear function inputs, local names, explicit dependencies, and careful state ownership.

---

# Lesson Map

Today's Lesson

1. Function Calls Create Local Names
2. Pass by Object Reference
3. Call by Sharing
4. Mutable vs Immutable in Function Calls
5. Mutation vs Rebinding
6. `append()` vs `+`
7. Common Mutable Methods
8. FastAPI Connections
9. Playwright Connections
10. AI Backend Connections
11. Interview Review
12. Today's Takeaway

---

# Estimated Study Time

Reading: 80-110 minutes

Exercises: 60-90 minutes

Coding: 45-60 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Main Concepts

## Function Calls Create Local Names

When Python calls a function, it creates local parameter names inside that function.

Example:

```python
def show_name(name: str) -> None:
    print(name)


user_name = "Alice"
show_name(user_name)
```

Inside the function, `name` is a local name.

Outside the function, `user_name` is another name.

Both names can point to the same object during the function call.

Memory model:

```text
outside:

user_name ----+
              |
              v
          "Alice"
              ^
              |
inside:

name ---------+
```

This does not mean the function receives a box containing the variable.

It receives a reference to the object.

## Pass by Object Reference

Python's parameter passing model is often described as:

```text
pass by object reference
```

More precisely, Python passes object references by value.

That means:

* The function gets a local parameter name.
* The local name points to the same object as the argument.
* Rebinding the local name does not rebind the caller's name.
* Mutating the shared object can be visible to the caller.

Example:

```python
def add_item(items: list[str]) -> None:
    items.append("fastapi")


topics = ["python"]
add_item(topics)

print(topics)
```

Output:

```text
['python', 'fastapi']
```

Why?

```text
topics ----+
          |
          v
items -> list object: ["python", "fastapi"]
```

The parameter `items` and the caller name `topics` point to the same list.

## Call by Sharing

The phrase "call by sharing" is useful for interviews.

It means the caller and the function share access to the same object.

The function cannot directly reassign the caller's variable name.

But the function can mutate the object if the object is mutable.

Compare these two functions:

```python
def mutate(items: list[int]) -> None:
    items.append(3)


def rebind(items: list[int]) -> None:
    items = items + [3]
```

Now test:

```python
numbers = [1, 2]
mutate(numbers)
print(numbers)

numbers = [1, 2]
rebind(numbers)
print(numbers)
```

Output:

```text
[1, 2, 3]
[1, 2]
```

The first function mutates the shared list.

The second function creates a new list and rebinds only the local name `items`.

## Mutable Objects in Function Calls

Mutable objects can be changed inside a function.

Common mutable objects:

* `list`
* `dict`
* `set`
* most custom class instances

Example:

```python
def add_role(user: dict[str, str]) -> None:
    user["role"] = "admin"


profile = {"name": "Alice"}
add_role(profile)

print(profile)
```

Output:

```text
{'name': 'Alice', 'role': 'admin'}
```

The function did not return anything.

But the caller can still see the mutation.

Engineering meaning:

```text
If a function mutates a parameter, the function is changing caller-owned state.
```

That may be acceptable, but it must be intentional.

## Immutable Objects in Function Calls

Immutable objects cannot be changed in place.

Example:

```python
def increment(value: int) -> None:
    value = value + 1


score = 10
increment(score)

print(score)
```

Output:

```text
10
```

Inside the function, `value = value + 1` creates a new integer object and rebinds the local name `value`.

The caller's name `score` still points to the original integer object.

Memory model:

```text
Before rebinding:

score ----+
         |
         v
value -> 10

After rebinding inside function:

score -> 10

value -> 11
```

The caller is not changed.

## Mutation vs Rebinding

Mutation changes an object.

Rebinding changes what a name points to.

Example:

```python
def mutate(items: list[int]) -> None:
    items.append(3)


def rebind(items: list[int]) -> None:
    items = [1, 2, 3]
```

Mutation:

```text
caller_name ----+
                |
                v
parameter  -> same list object, modified
```

Rebinding:

```text
caller_name -> original object

parameter   -> new object
```

Interview rule:

```text
Rebinding a parameter never changes the caller's variable binding.
Mutating a shared mutable object can change what the caller observes.
```

## `append()` vs `+`

This was one of today's key classroom distinctions.

`append()` mutates the list in place.

```python
def add_with_append(items: list[int]) -> None:
    items.append(3)


numbers = [1, 2]
add_with_append(numbers)
print(numbers)
```

Output:

```text
[1, 2, 3]
```

`+` creates a new list.

```python
def add_with_plus(items: list[int]) -> None:
    items = items + [3]


numbers = [1, 2]
add_with_plus(numbers)
print(numbers)
```

Output:

```text
[1, 2]
```

Why?

```text
append():

items -> same list object, changed

+:

items -> new list object
```

If you want the caller to receive the new list, return it:

```python
def add_with_return(items: list[int]) -> list[int]:
    return items + [3]


numbers = [1, 2]
numbers = add_with_return(numbers)
print(numbers)
```

Output:

```text
[1, 2, 3]
```

## Common Mutable Methods

These methods usually mutate the object in place:

| Type | Methods |
|------|---------|
| `list` | `append`, `extend`, `insert`, `remove`, `pop`, `sort`, `reverse`, `clear` |
| `dict` | `update`, `setdefault`, `pop`, `clear` |
| `set` | `add`, `update`, `remove`, `discard`, `clear` |

This matters in function calls because these methods can change caller-visible state.

Example:

```python
def normalize_tags(tags: list[str]) -> None:
    tags.sort()


user_tags = ["fastapi", "python"]
normalize_tags(user_tags)

print(user_tags)
```

Output:

```text
['fastapi', 'python']
```

The function sorted the caller's list in place.

If that is intended, the function name should make mutation clear.

If that is not intended, return a new list:

```python
def sorted_tags(tags: list[str]) -> list[str]:
    return sorted(tags)
```

---

# Engineering Thinking

## Function Boundaries Are Ownership Boundaries

When a function receives an object, the engineering question is:

```text
Does this function own the object, or is it borrowing it?
```

If the function only borrows the object, mutation should be avoided or clearly documented.

If the function owns the object, mutation may be acceptable.

This is exactly how senior engineers review Python code.

They do not only ask:

```text
Does it work?
```

They ask:

```text
Who owns this state?
Can this mutation surprise the caller?
Will this break when requests or jobs run concurrently?
```

## Tech Lead Questions

Question:

Why does rebinding a parameter not affect the caller?

Think first.

Expected student answer:

Because the parameter is a local name inside the function. Rebinding changes the local name,
not the caller's name.

Explanation:

The caller's variable and the function parameter are different names. They may point to the same object at first, but rebinding the parameter only changes the local binding.

Question:

Why can `append()` affect the caller?

Expected student answer:

Because the parameter and the caller's name can point to the same list object. `append()` mutates that shared object.

Explanation:

The function does not need to rebind the caller's name. The caller sees the changed list because both names shared the object.

Question:

Should every function avoid mutation?

Expected student answer:

No. Mutation is acceptable when it is intentional, local, and clearly communicated.

Explanation:

Production code should make mutation obvious. Hidden mutation is the problem.

---

# Classroom Exercises

## Exercise 1: Output Prediction

Question:

What prints?

```python
def add_item(items: list[int]) -> None:
    items.append(3)


values = [1, 2]
add_item(values)
print(values)
```

Think first.

Expected student answer:

```text
[1, 2, 3]
```

Explanation:

`items` and `values` point to the same list. `append()` mutates that list in place.

## Exercise 2: Rebinding

Question:

What prints?

```python
def add_item(items: list[int]) -> None:
    items = items + [3]


values = [1, 2]
add_item(values)
print(values)
```

Expected student answer:

```text
[1, 2]
```

Explanation:

`items + [3]` creates a new list. The local name `items` points to that new list, but `values` still points to the original list.

## Exercise 3: `id()` Reasoning

Question:

Which `id()` values are equal?

```python
def inspect(items: list[int]) -> None:
    print(id(items))
    items.append(3)
    print(id(items))


values = [1, 2]
print(id(values))
inspect(values)
print(id(values))
```

Expected student answer:

All printed IDs are the same.

Explanation:

No rebinding happens. `append()` mutates the same list object.

## Exercise 4: `append()` vs `+`

Question:

Fix this function so the caller receives the new list:

```python
def add_score(scores: list[int]) -> None:
    scores = scores + [100]
```

Expected student answer:

```python
def add_score(scores: list[int]) -> list[int]:
    return scores + [100]
```

Explanation:

If the function creates a new list, it must return the new object to the caller.

## Exercise 5: FastAPI Parameter Sharing

Question:

What is wrong with this code?

```python
shared_filters: dict[str, str] = {}


def build_filters(user_id: str) -> dict[str, str]:
    shared_filters["user_id"] = user_id
    return shared_filters
```

Expected student answer:

The function mutates and returns a shared global dictionary.

Explanation:

In a FastAPI app, multiple requests could share this object. One user's filter data could overwrite another user's data.

## Exercise 6: Playwright Page Lifecycle

Question:

Why is this risky?

```python
async def login(page, email: str) -> None:
    await page.fill("#email", email)
```

Expected student answer:

The function mutates browser page state. It is only safe if the caller owns the page lifecycle and the page is not shared across unrelated jobs.

Explanation:

Playwright `Page` objects represent live mutable external state. Passing them into functions is normal, but ownership must be clear.

## Exercise 7: AI Backend Messages

Question:

What bug can happen here?

```python
def add_user_message(messages: list[dict[str, str]], content: str) -> None:
    messages.append({"role": "user", "content": content})
```

Expected student answer:

The function mutates the caller's `messages` list. If that list is shared across users, conversations can mix.

Explanation:

AI message history must be scoped by user and session. Mutating shared state can cause prompt pollution.

---

# FastAPI Connections

FastAPI route handlers and dependencies are functions.

That means parameter passing rules apply everywhere.

Bad example:

```python
from fastapi import FastAPI

app = FastAPI()
shared_tags: list[str] = []


@app.post("/tags")
def add_tag(tag: str) -> dict[str, list[str]]:
    shared_tags.append(tag)
    return {"tags": shared_tags}
```

Problem:

`shared_tags` is a mutable object shared by all requests.

Better example:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class TagRequest(BaseModel):
    tag: str


@app.post("/tags")
def add_tag(payload: TagRequest) -> dict[str, str]:
    return {"tag": payload.tag}
```

The route handles request-local data and returns a response.

If data must persist, use a database or cache with clear ownership.

Engineering rule:

```text
FastAPI dependencies and route handlers should not hide request-specific mutation in shared objects.
```

Why Day03 matters:

When a dependency receives a list, dictionary, database session, or settings object, the team must know whether the function mutates it or only reads from it.

---

# Playwright Connections

Playwright functions often receive `page` or `context` objects.

Those objects are mutable handles to browser state.

Example:

```python
async def search(page, keyword: str) -> None:
    await page.fill("#search", keyword)
    await page.click("button[type='submit']")
```

This function mutates page state by typing and clicking.

That is normal.

The engineering question is:

```text
Who owns the page?
```

Risky design:

```python
shared_pages = []


async def save_page(page) -> None:
    shared_pages.append(page)
```

Problem:

The function stores a mutable external resource in shared state. This can create memory leaks, cross-job confusion, and lifecycle bugs.

Better design:

```python
async def run_job(context, keyword: str) -> None:
    page = await context.new_page()
    try:
        await search(page, keyword)
    finally:
        await page.close()
```

Engineering rule:

```text
Passing a Playwright object into a function is fine.
Sharing its lifecycle accidentally is not fine.
```

---

# AI Backend Connections

AI backend systems pass message history and state through functions constantly.

Example:

```python
def add_user_message(messages: list[dict[str, str]], content: str) -> None:
    messages.append({"role": "user", "content": content})
```

This function mutates the caller's list.

That can be correct if `messages` belongs to one user session.

It is dangerous if `messages` is shared across users.

Risky design:

```python
shared_messages: list[dict[str, str]] = []


def chat(content: str) -> list[dict[str, str]]:
    shared_messages.append({"role": "user", "content": content})
    return shared_messages
```

Problem:

Every caller shares the same mutable conversation history.

Better design:

```python
def add_user_message(
    messages: list[dict[str, str]],
    content: str,
) -> list[dict[str, str]]:
    return messages + [{"role": "user", "content": content}]
```

This returns a new list instead of mutating the caller's list.

Engineering rule:

```text
AI conversation state must be scoped by user and session.
Function boundaries should make state mutation explicit.
```

Why Day03 matters:

Parameter passing explains why a small helper can accidentally pollute prompt history.

---

# English Interview

## Key Vocabulary

* parameter passing
* object reference
* call by sharing
* mutation
* rebinding
* caller-visible state
* function boundary
* ownership

## Example Answer: How Python Passes Parameters

Python passes object references by value. A function parameter is a local name that points
to the same object as the argument. If the function mutates a shared mutable object,
the caller can observe the change. If the function rebinds the parameter,
only the local name changes.

## Example Answer: Call by Sharing

Call by sharing means the caller and the function share access to the same object.
The function cannot reassign the caller's variable, but it can mutate the shared object
if that object is mutable.

## Example Answer: Mutation vs Rebinding

Mutation changes the object itself. Rebinding changes which object a local name points to.
This is why `append()` can affect the caller, while `items = items + [3]` does not affect
the caller unless the new list is returned.

---

# Today's Takeaway

Today's core idea:

```text
Function parameters are local names pointing to objects.
Mutation can affect shared objects.
Rebinding affects only the local name.
```

Production rule:

```text
When passing mutable objects into functions, make ownership and mutation explicit.
```

This explains why FastAPI request state, Playwright browser objects, and AI conversation histories must have clear boundaries.

---

# Before Next Lesson Checklist

Students should confirm they can answer these questions without looking at the notes.

- [ ] How does Python pass function arguments?
- [ ] What does call by sharing mean?
- [ ] Why can `append()` affect the caller?
- [ ] Why does `items = items + [3]` not affect the caller's variable?
- [ ] What is the difference between mutation and rebinding?
- [ ] Which common list methods mutate in place?
- [ ] How can `id()` help explain parameter passing?
- [ ] Why can mutable parameters create FastAPI bugs?
- [ ] Why does Playwright page ownership matter?
- [ ] Why can shared AI `messages` state cause prompt pollution?

---

# Homework

## Mini Exercises

1. Predict the output of five function calls that use `append()`, `+`, and rebinding.
2. Use `id()` before, during, and after a function call to explain object identity.
3. Rewrite one mutating function into a pure function that returns a new object.
4. Explain one FastAPI shared-state bug in your own words.
5. Explain one Playwright page lifecycle bug in your own words.
6. Explain one AI backend `messages` state bug in your own words.

## Repository Task

After completing this lesson, synchronize:

* `docs/python/day03-functions-parameter-passing.md`
* `cheat_sheets/python.md`
* `interview/python.md`
* `PROJECT_STATUS.md`
* `TASKS.md`
* `CHANGELOG.md`
