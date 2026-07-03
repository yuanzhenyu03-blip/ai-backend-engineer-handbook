# Python Interview

## Purpose

This document is the template for all future interview handbooks in this repository. It prepares the student to answer Python questions in overseas AI Backend Engineer interviews with engineering reasoning, not memorized definitions.

---

## Knowledge Checklist

Before using this interview sheet, make sure you can explain:

- Python object model
- Variables and references
- Object identity
- `==` vs `is`
- Mutable vs immutable objects
- Mutable default argument bug
- Function objects
- Callable objects
- `__call__`
- Iterator and iterable protocol
- Generators and `yield`
- Decorators and closures
- Context managers
- Async, await, and event loop basics
- Type hints
- Error handling
- Testing habits

---

## Beginner Questions

### 1. What does it mean that everything in Python is an object?

Expected answer:

In Python, values such as integers, strings, lists, dictionaries, functions, classes, and modules are objects. Each object has identity, type, and value. Variables do not directly store the object; they are names bound to object references.

Follow-up questions:

- How can you check an object's type?
- How can you check an object's identity?
- Are functions objects too?

### 2. What is the difference between `==` and `is`?

Expected answer:

`==` checks value equality. `is` checks object identity, meaning whether two names point to the exact same object. In production code, I use `==` for normal value comparison and `is` for identity checks such as `value is None`.

Follow-up questions:

- Why is `is None` preferred over `== None`?
- Why should we not use `is` for string comparison?

### 3. Why are mutable default arguments dangerous?

Expected answer:

Default argument values are evaluated once when the function is defined. If the default is a mutable object such as a list or dictionary, all calls that use the default share the same object. This can leak state between calls.

Follow-up questions:

- How do you fix this bug?
- Why does this matter in a web API?

### 4. Are functions first-class objects in Python?

Expected answer:

Yes. Functions can be assigned to variables, passed as arguments, returned from other functions, and stored in data structures. This is important for decorators, dependency injection, callbacks, and AI tool registries.

Follow-up questions:

- How does FastAPI use function objects?
- How could an AI backend store tools as functions?

---

## Intermediate Questions

### 1. Explain Python's reference model.

Expected answer:

A Python variable is a name bound to a reference to an object. Assignment copies the reference, not necessarily the object. If two names refer to the same mutable object, mutating through one name is visible through the other.

Follow-up questions:

- How do you avoid accidental shared mutation?
- When should you copy an object?

### 2. What is a callable object?

Expected answer:

A callable object is any object that can be called with parentheses. Functions are callable. Classes are callable because calling a class creates an instance. Instances can be callable if their class implements `__call__`.

Follow-up questions:

- When would you use a callable class instead of a function?
- How can callable objects support dependency injection?

### 3. What is the difference between an iterator and an iterable?

Expected answer:

An iterable is an object that can return an iterator, usually through `__iter__`. An iterator is an object that returns values one at a time using `__next__`. Iterators remember their current position.

Follow-up questions:

- Why are iterators useful for large data?
- How does this connect to streaming APIs?

### 4. What problem do generators solve?

Expected answer:

Generators allow lazy evaluation. They produce values one at a time instead of building the entire result in memory. This is useful for streaming data, processing large files, and building memory-efficient pipelines.

Follow-up questions:

- What does `yield` do?
- When would a generator be better than a list?

---

## Senior Questions

### 1. How can Python's flexibility become a production risk?

Expected answer:

Python is flexible, but without discipline it can lead to hidden mutable state, weak boundaries, runtime errors, and unclear ownership. Production Python needs type hints, tests, readable structure, explicit dependencies, logging, and clear error handling.

Follow-up questions:

- How would you enforce quality in a Python team?
- What would you reject in code review?

### 2. How does Python's object model influence framework design?

Expected answer:

Frameworks use Python objects and protocols heavily. FastAPI uses function objects, annotations, and callables for routing and dependency injection. Playwright exposes browser, context, page, and locator as objects that represent external state. Understanding the object model helps engineers design safe abstractions.

Follow-up questions:

- Why does FastAPI inspect type hints?
- Why should Playwright browser contexts be isolated?

### 3. How would you explain Python's performance trade-off to a CTO?

Expected answer:

Python is usually chosen for AI backend work because it maximizes developer productivity and has a strong AI ecosystem. Heavy compute often runs in optimized libraries or external model services. Python orchestrates APIs, queues, databases, automation, and model calls. The trade-off is managed through profiling, async I/O, caching, background jobs, and moving hot paths when needed.

Follow-up questions:

- When would you not use Python?
- How would you scale a Python backend?

---

## Day02 Questions: Mutable vs Immutable

### 1. What is the difference between mutable and immutable objects?

Question:

What is the difference between mutable and immutable objects in Python?

Answer:

A mutable object can be changed after it is created. Examples include `list`, `dict`, and `set`. An immutable object cannot be changed after it is created. Examples include `int`, `str`, `bool`, and many tuples.

Explanation:

The important engineering distinction is whether the object itself can change. Reassigning a variable is not mutation. Reassignment binds a name to another object. Mutation changes the object that existing references already point to.

Backend scenario:

Shared mutable objects can leak state between FastAPI requests, Playwright jobs, or AI chat sessions.

### 2. Does `b = a` copy a list?

Question:

If `a` is a list and we write `b = a`, do we copy the list?

Answer:

No. `b = a` copies the reference. Both names point to the same list object.

Explanation:

If either `a` or `b` mutates the list, the other name sees the change because there is only one list object.

Example:

```python
a = [1, 2]
b = a
b.append(3)

print(a)  # [1, 2, 3]
```

Backend scenario:

If two requests or jobs share the same mutable list, one request can affect another request's data.

### 3. What is `id()` used for?

Question:

How can `id()` help explain Python object identity?

Answer:

`id()` returns an object's identity during its lifetime. It can be used in learning experiments to check whether two names point to the same object.

Explanation:

If `id(a) == id(b)`, then `a` and `b` refer to the same object. In normal production code, we usually design clear ownership instead of relying on printed IDs.

Backend scenario:

Understanding identity helps debug shared state bugs in request handlers, automation workers, and AI session managers.

### 4. What is the difference between `append()`, `a += [...]`, and `a = a + [...]` for lists?

Question:

Compare `append()`, `+=`, and `a = a + [...]` for Python lists.

Answer:

`append()` mutates the existing list in place. For lists, `+=` also mutates the existing list in place. `a = a + [...]` creates a new list and rebinds the name `a` to that new object.

Explanation:

The difference matters when another name points to the original list. In-place mutation is visible through all references. Rebinding is not.

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

Backend scenario:

A helper that mutates a shared list can unexpectedly change caller-owned state.

### 5. What is shallow copy?

Question:

What does `copy.copy()` do?

Answer:

`copy.copy()` creates a shallow copy. It copies the first layer of the object, but nested mutable objects may still be shared.

Explanation:

If the object contains nested lists or dictionaries, the outer container may be new while the inner objects are still shared.

Example:

```python
import copy

original = [["python"]]
cloned = copy.copy(original)
cloned[0].append("fastapi")

print(original)  # [['python', 'fastapi']]
```

Backend scenario:

Shallow copying a request payload or configuration object can still share nested mutable state.

### 6. What is deep copy?

Question:

What does `copy.deepcopy()` do?

Answer:

`copy.deepcopy()` recursively copies the object tree so nested objects are copied too.

Explanation:

Deep copy creates stronger isolation than shallow copy, but it can be more expensive in memory and time.

Backend scenario:

Deep copy can be useful when a job needs full isolation from the original data, but it should not be used blindly to hide unclear ownership.

### 7. Why are lists, dictionaries, and sets unhashable?

Question:

Why can't `list`, `dict`, or `set` be used as dictionary keys?

Answer:

They are mutable and therefore unhashable. Dictionary keys need stable hash values. If a key could change after insertion, the dictionary could no longer reliably find the value.

Explanation:

Hashability requires stability. Mutable containers can change their contents, so Python prevents them from being used as dictionary keys.

Backend scenario:

Cache keys, deduplication keys, and dictionary indexes should use stable values such as strings, integers, or safe tuples.

### 8. Can a tuple always be used as a dictionary key?

Question:

Can every tuple be used as a dictionary key?

Answer:

No. A tuple can be used as a dictionary key only if every value inside it is also hashable.

Explanation:

The tuple itself is immutable, but if it contains a list, the overall tuple is unhashable because the nested list is mutable.

Example:

```python
valid_key = ("user", 1)
invalid_key = ("user", [1, 2])
```

Backend scenario:

When designing cache keys, use fully hashable structures. Do not put lists or dictionaries inside tuple keys.

### 9. How does mutability affect FastAPI applications?

Question:

How can mutable objects cause bugs in FastAPI?

Answer:

Mutable global objects can be shared across requests. If request-specific data is stored in a global list or dictionary, one user's data can leak into another user's request.

Explanation:

FastAPI applications handle many requests over time. Shared mutable state must be explicit and carefully managed. Request-specific state should be scoped to the request or stored in a database with clear ownership.

Backend scenario:

Never store user-specific request data in a global list.

### 10. How does mutability affect Playwright automation?

Question:

How can shared mutable objects break Playwright jobs?

Answer:

Sharing page, context, cookies, headers, or storage state across unrelated jobs can cause job state to mix. One job may overwrite another job's authentication or browser state.

Explanation:

Playwright objects represent live external state. Automation jobs should isolate browser contexts and avoid shared mutable configuration unless sharing is intentional.

Backend scenario:

Create isolated contexts for unrelated login or scraping jobs.

### 11. How does mutability affect AI backend systems?

Question:

How can shared mutable state break an AI backend?

Answer:

If multiple users share the same `messages`, `history`, or `state` list, conversations can mix. This can cause prompt pollution, privacy issues, and incorrect model responses.

Explanation:

AI memory must be scoped by user and session. Mutable conversation history should not be global unless it is intentionally shared and protected.

Backend scenario:

Store conversation history per user/session in a database or cache, not in one global list.

---

## Enterprise Scenarios

### Scenario 1: FastAPI Dependency Leak

Problem:

A developer stores request-specific state in a global dictionary.

Risk:

Multiple requests can share state accidentally, causing user data leaks.

Expected solution:

Use request-scoped dependencies, explicit parameters, or properly managed context. Avoid global mutable state.

### Scenario 2: Playwright Shared Page Object

Problem:

A background worker shares one Playwright page across unrelated jobs.

Risk:

Browser state, cookies, navigation, and DOM state can leak between jobs.

Expected solution:

Create isolated browser contexts per job and close them reliably.

### Scenario 3: AI Tool Registry

Problem:

An AI backend needs to map model tool calls to Python behavior.

Expected solution:

Use a dictionary mapping tool names to typed callable functions. Validate inputs before calling tools and return structured outputs.

---

## English Interview Answers

### Explain Python's object model.

Python's object model means that values such as integers, strings, lists, functions, and classes are objects. Each object has identity, type, and value. Variables are names bound to references, not containers that directly hold the object. This model is important because it explains function objects, shared mutable state, and identity comparison.

### Explain mutable default arguments.

Mutable default arguments are dangerous because default values are evaluated once when the function is defined. If the default is a list or dictionary, multiple calls can share the same object. In production code, I use `None` as the default and create a new object inside the function.

### Explain why Python is used in AI backend systems.

Python is popular in AI backend systems because it is readable, productive, and has a strong ecosystem for AI, data, APIs, and automation. It is often used as the orchestration layer that connects models, databases, queues, and external services.

---

## Common Mistakes

- Using `is` instead of `==` for value comparison.
- Using mutable default arguments.
- Mutating caller-owned data without making it clear.
- Writing functions without type hints.
- Treating Python scripts as production architecture.
- Confusing database identity with Python object identity.
- Sharing Playwright browser state across unrelated jobs.
- Hiding dependencies in global variables.

---

## Cheat Sheet

- `==` compares value.
- `is` compares identity.
- Use `is None` for `None` checks.
- Functions are objects.
- Callable objects implement `__call__`.
- Variables are names bound to references.
- Mutable defaults are shared across calls.
- Prefer explicit dependencies over global state.
- Use type hints for public functions.
- Production Python requires tests, logging, and clear structure.
