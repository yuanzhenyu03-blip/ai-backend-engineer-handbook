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
