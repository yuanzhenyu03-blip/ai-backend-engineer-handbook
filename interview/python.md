# Python Interview

## Purpose

This document is the template for all future interview handbooks in this repository.
It prepares the student to answer Python questions in overseas AI Backend Engineer interviews
with engineering reasoning, not memorized definitions.

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

In Python, values such as integers, strings, lists, dictionaries, functions, classes,
and modules are objects. Each object has identity, type, and value. Variables do not
directly store the object; they are names bound to object references.

Follow-up questions:

- How can you check an object's type?
- How can you check an object's identity?
- Are functions objects too?

### 2. What is the difference between `==` and `is`?

Expected answer:

`==` checks value equality. `is` checks object identity, meaning whether two names point
to the exact same object. In production code, I use `==` for normal value comparison
and `is` for identity checks such as `value is None`.

Follow-up questions:

- Why is `is None` preferred over `== None`?
- Why should we not use `is` for string comparison?

### 3. Why are mutable default arguments dangerous?

Expected answer:

Default argument values are evaluated once when the function is defined. If the default
is a mutable object such as a list or dictionary, all calls that use the default share
the same object. This can leak state between calls.

Follow-up questions:

- How do you fix this bug?
- Why does this matter in a web API?

### 4. Are functions first-class objects in Python?

Expected answer:

Yes. Functions can be assigned to variables, passed as arguments, returned from other
functions, and stored in data structures. This is important for decorators, dependency
injection, callbacks, and AI tool registries.

Follow-up questions:

- How does FastAPI use function objects?
- How could an AI backend store tools as functions?

---

## Intermediate Questions

### 1. Explain Python's reference model.

Expected answer:

A Python variable is a name bound to a reference to an object. Assignment copies the
reference, not necessarily the object. If two names refer to the same mutable object,
mutating through one name is visible through the other.

Follow-up questions:

- How do you avoid accidental shared mutation?
- When should you copy an object?

### 2. What is a callable object?

Expected answer:

A callable object is any object that can be called with parentheses. Functions are callable.
Classes are callable because calling a class creates an instance. Instances can be callable
if their class implements `__call__`.

Follow-up questions:

- When would you use a callable class instead of a function?
- How can callable objects support dependency injection?

### 3. What is the difference between an iterator and an iterable?

Expected answer:

An iterable is an object that can return an iterator, usually through `__iter__`.
An iterator is an object that returns values one at a time using `__next__`.
Iterators remember their current position.

Follow-up questions:

- Why are iterators useful for large data?
- How does this connect to streaming APIs?

### 4. What problem do generators solve?

Expected answer:

Generators allow lazy evaluation. They produce values one at a time instead of building
the entire result in memory. This is useful for streaming data, processing large files,
and building memory-efficient pipelines.

Follow-up questions:

- What does `yield` do?
- When would a generator be better than a list?

---

## Senior Questions

### 1. How can Python's flexibility become a production risk?

Expected answer:

Python is flexible, but without discipline it can lead to hidden mutable state,
weak boundaries, runtime errors, and unclear ownership. Production Python needs type hints,
tests, readable structure, explicit dependencies, logging, and clear error handling.

Follow-up questions:

- How would you enforce quality in a Python team?
- What would you reject in code review?

### 2. How does Python's object model influence framework design?

Expected answer:

Frameworks use Python objects and protocols heavily. FastAPI uses function objects,
annotations, and callables for routing and dependency injection. Playwright exposes browser,
context, page, and locator as objects that represent external state. Understanding the object
model helps engineers design safe abstractions.

Follow-up questions:

- Why does FastAPI inspect type hints?
- Why should Playwright browser contexts be isolated?

### 3. How would you explain Python's performance trade-off to a CTO?

Expected answer:

Python is usually chosen for AI backend work because it maximizes developer productivity
and has a strong AI ecosystem. Heavy compute often runs in optimized libraries or external
model services. Python orchestrates APIs, queues, databases, automation, and model calls.
The trade-off is managed through profiling, async I/O, caching, background jobs,
and moving hot paths when needed.

Follow-up questions:

- When would you not use Python?
- How would you scale a Python backend?

---

## Day02 Questions: Mutable vs Immutable

### 1. What is the difference between mutable and immutable objects?

Question:

What is the difference between mutable and immutable objects in Python?

Answer:

A mutable object can be changed after it is created. Examples include `list`, `dict`,
and `set`. An immutable object cannot be changed after it is created. Examples include
`int`, `str`, `bool`, and many tuples.

Explanation:

The important engineering distinction is whether the object itself can change.
Reassigning a variable is not mutation. Reassignment binds a name to another object.
Mutation changes the object that existing references already point to.

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

`append()` mutates the existing list in place. For lists, `+=` also mutates the existing
list in place. `a = a + [...]` creates a new list and rebinds the name `a` to that new object.

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

FastAPI applications handle many requests over time. Shared mutable state must be explicit
and carefully managed. Request-specific state should be scoped to the request or stored
in a database with clear ownership.

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

## Day03 Questions: Functions & Parameter Passing

### Beginner 1. How does Python pass function arguments?

Question:

How does Python pass parameters into a function?

Answer:

Python passes object references by value. A function parameter is a local name that points
to the same object passed by the caller.

Explanation:

The function does not receive the caller's variable itself. It receives a reference to the
object. Rebinding the parameter changes only the local name, but mutating a shared mutable
object can be visible to the caller.

Backend scenario:

This explains why a helper function can accidentally mutate a request payload, Playwright
page state, or AI message history.

### Beginner 2. What is the difference between `append()` and `+`?

Question:

What is the difference between `append()` and `+` for a list parameter?

Answer:

`append()` mutates the existing list in place. `+` creates a new list.

Explanation:

If a function calls `items.append(value)`, the caller can see the change because the list
object is shared. If a function does `items = items + [value]`, only the local name is
rebound to a new list.

Example:

```python
def mutate(items: list[int]) -> None:
    items.append(3)


def rebind(items: list[int]) -> None:
    items = items + [3]
```

Backend scenario:

This distinction matters when deciding whether a function should mutate caller-owned state
or return a new object.

### Intermediate 1. Why can a list be modified inside a function but an int cannot?

Question:

Why can a function modify a list argument but not modify an integer argument in place?

Answer:

A list is mutable, so methods such as `append()` can change the list object in place.
An integer is immutable, so operations such as `value + 1` create a new integer object.

Explanation:

Both arguments are passed as object references. The difference is the object's mutability.
The list can change internally. The integer cannot.

Backend scenario:

Mutable objects passed into service functions require clear ownership. Immutable values are
safer to share because they cannot be changed in place.

### Intermediate 2. What is the difference between mutation and rebinding?

Question:

Explain mutation vs rebinding in Python function calls.

Answer:

Mutation changes the object itself. Rebinding changes what a local name points to.

Explanation:

If a parameter points to a list and the function calls `append()`, the list object changes.
If the function assigns `items = items + [3]`, the local name `items` points to a new list,
but the caller's name still points to the original list.

Backend scenario:

Hidden mutation can create bugs across FastAPI requests, Playwright jobs, and AI sessions.
Rebinding can create a different bug: the engineer expects the caller to change, but it does not.

### Senior 1. Explain call by sharing.

Question:

Explain Python's parameter passing model using the term call by sharing.

Answer:

Call by sharing means the caller and the function share access to the same object.
The function parameter is a local name bound to that object. The function cannot reassign
the caller's variable, but it can mutate the shared object if the object is mutable.

Explanation:

This model is why Python does not behave like pure pass-by-value or pure pass-by-reference.
Object identity is shared, but variable bindings are local.

Backend scenario:

Call by sharing explains why state ownership must be explicit in backend service layers.

### Senior 2. Why doesn't rebinding affect the caller?

Question:

Why does rebinding a parameter inside a function not affect the caller's variable?

Answer:

Because the parameter is a local name inside the function. Rebinding changes that local name.
It does not change the caller's separate name.

Explanation:

At the beginning of the call, both names may point to the same object. After rebinding,
the function parameter points to a new object while the caller's name still points to the
original object.

Backend scenario:

If a function builds a new list, dictionary, or message history, it must return the new
object if the caller should use it.

### Senior 3. How does Python's parameter passing model affect FastAPI, Playwright, and AI Backend?

Question:

How does Python's parameter passing model affect FastAPI, Playwright, and AI backend systems?

Answer:

Python functions receive local names pointing to objects. If those objects are mutable,
the function may change caller-visible state. In FastAPI, this can leak request data.
In Playwright, this can mutate page or context state. In AI backends, this can pollute
shared `messages`, `history`, or session state.

Explanation:

The engineering issue is ownership. A function boundary should make it clear whether the
function reads an object, mutates it, or returns a new object.

Backend scenario:

Production code should avoid hidden mutation, isolate request/job/session state, and return
new objects when creating new state.

---

## Day04 Questions: Scope & LEGB

### Beginner 1. What is LEGB?

Question:

What does LEGB mean in Python?

Answer:

LEGB is Python's name lookup order: Local, Enclosing, Global, and Built-in.

Explanation:

When Python sees a name, it first checks the current local scope, then enclosing function
scopes, then module global scope, then built-in names.

Follow-up questions:

- What is an enclosing scope?
- Where does Python find `len`?

### Beginner 2. What is lexical scope?

Question:

What does it mean that Python uses lexical scope?

Answer:

Lexical scope means a function resolves names based on where the function is defined,
not where it is called.

Explanation:

The function's enclosing scope is determined by the code structure. A caller does not become
the enclosing scope just because it calls the function.

Follow-up questions:

- How is lexical scope different from dynamic scope?
- Why is lexical scope easier to reason about in production?

### Intermediate 1. Why does `count = count + 1` raise `UnboundLocalError`?

Question:

Why does this code fail?

```python
count = 0


def add():
    count = count + 1
```

Answer:

Python treats `count` as a local variable inside `add()` because there is an assignment
to `count` in the function body. Then it tries to read the local `count` before it has
a value.

Explanation:

Python determines local variables at compile time. Assignment inside a function makes the
name local unless `global` or `nonlocal` is declared.

Follow-up questions:

- How does `global count` change the behavior?
- Why should this be avoided for request state?

### Intermediate 2. What is the difference between `global` and `nonlocal`?

Question:

Explain `global` vs `nonlocal`.

Answer:

`global` binds a name in module global scope. `nonlocal` binds a name in the nearest
enclosing function scope.

Explanation:

Use `global` when rebinding a module-level name. Use `nonlocal` when rebinding a name from
an outer function. Both should be used carefully because they can hide state changes.

Follow-up questions:

- Why does `nonlocal` not refer to global scope?
- When is `nonlocal` useful?

### Intermediate 3. Why does `append()` not require `global` or `nonlocal`?

Question:

Why does this work without `global`?

```python
items = []


def add():
    items.append(1)
```

Answer:

Because `append()` mutates the list object. It does not rebind the name `items`.

Explanation:

Python only needs `global` or `nonlocal` when a function rebinds a name from another scope.
Mutation changes the object, not the binding.

Follow-up questions:

- Why does `items = items + [1]` behave differently?
- How can hidden mutation become a production bug?

### Senior 1. Define closure in engineering terms.

Question:

What is a closure?

Answer:

A closure is a function object plus a captured environment.

Explanation:

The returned function preserves access to variables from the scope where it was defined,
even after the outer function has returned.

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

Follow-up questions:

- Why does `counter()` return `1`, then `2`, then `3`?
- What are the risks of closures that capture mutable state?

### Senior 2. Explain late binding.

Question:

Why do functions created in a loop often return the final loop value?

Answer:

Closures use late binding. They look up the captured variable when the function is called,
not when the function is created.

Explanation:

If multiple functions capture the same loop variable, they all see its final value after
the loop ends. The default argument pattern `def f(i=i): return i` captures the current
value at function definition time.

Follow-up questions:

- Why does `def f(i=i)` fix the problem?
- How can late binding affect callback generation?

### Senior 3. How does scope affect FastAPI, Playwright, and AI Backend systems?

Question:

How do scope rules affect backend systems?

Answer:

Scope controls where state comes from. Hidden global state can leak request data in FastAPI,
mix browser jobs in Playwright, and pollute AI conversation state.

Explanation:

Production systems should make state ownership explicit. Request state, page state, and
conversation state should be scoped to the lifecycle that owns them.

Follow-up questions:

- Why should a FastAPI request user not be stored globally?
- Why should a Playwright `Page` not be global?
- How can closures help AI prompt builders?

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

Python's object model means that values such as integers, strings, lists, functions,
and classes are objects. Each object has identity, type, and value. Variables are names
bound to references, not containers that directly hold the object. This model is important
because it explains function objects, shared mutable state, and identity comparison.

### Explain mutable default arguments.

Mutable default arguments are dangerous because default values are evaluated once when
the function is defined. If the default is a list or dictionary, multiple calls can share
the same object. In production code, I use `None` as the default and create a new object
inside the function.

### Explain why Python is used in AI backend systems.

Python is popular in AI backend systems because it is readable, productive, and has a strong
ecosystem for AI, data, APIs, and automation. It is often used as the orchestration layer
that connects models, databases, queues, and external services.

### Explain Python's parameter passing model.

Python uses call by sharing. A function parameter is a local name that points to the same
object passed by the caller. If the function mutates a shared mutable object, the caller
can observe the change. If the function rebinds the parameter, only the local name changes.

### Explain mutation vs rebinding.

Mutation changes the object itself. Rebinding changes which object a name points to.
In function calls, mutation can affect caller-visible state, but rebinding a parameter
does not rebind the caller's variable.

### Explain Python's lexical scope.

Python uses lexical scope, which means a function resolves names based on where it is
defined, not where it is called. This makes code easier to reason about because a function's
dependencies are determined by the code structure, not by the runtime caller.

### Explain closure.

A closure is a function object plus a captured environment. It allows a function to preserve
access to variables from an outer scope even after the outer function has returned.

### Explain late binding.

Late binding means a closure looks up a captured variable when the function is called,
not when the function is created. This is why functions created in a loop can all return
the final loop value unless the current value is captured explicitly.

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
- Expecting parameter rebinding to change the caller's variable.
- Mutating function parameters without making ownership clear.
- Storing request state in global variables.
- Using `nonlocal` when simple mutation does not require rebinding.
- Forgetting late binding when creating functions in loops.

---

## Cheat Sheet

- `==` compares value.
- `is` compares identity.
- Use `is None` for `None` checks.
- Functions are objects.
- Callable objects implement `__call__`.
- Variables are names bound to references.
- Mutable defaults are shared across calls.
- Python uses call by sharing.
- `append()` mutates a list; `+` creates a new list.
- Rebinding a parameter does not rebind the caller's variable.
- LEGB means Local, Enclosing, Global, Built-in.
- Python uses lexical scope.
- Closure means function object plus captured environment.
- Late binding means variables are looked up when the closure is called.
- Prefer explicit dependencies over global state.
- Use type hints for public functions.
- Production Python requires tests, logging, and clear structure.
