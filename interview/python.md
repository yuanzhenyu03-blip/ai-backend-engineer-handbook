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

## Day05 Questions: Closures

### Beginner 1. What is a closure?

Question:

What is a closure in Python?

中文解析:

闭包不是简单的“函数里面定义函数”。工程上更准确的定义是：

```text
Closure = Function Object + Captured Environment
```

也就是说，一个函数对象被返回或稍后使用时，仍然保留了它定义时所需要的外层变量。

English answer:

A closure is a function object plus a captured environment. It allows a function to keep
access to variables from the scope where it was defined, even after the outer function has
returned.

Overseas backend interview answer:

In backend systems, I use closures when I need to create configured behavior without using
global state. For example, a factory function can capture configuration and return a
dependency, validator, or prompt builder.

Follow-up questions:

- Why is "a function inside another function" not a complete definition?
- What does the inner function capture?
- How can closure state become risky in production?

### Beginner 2. What is a captured environment?

Question:

What does captured environment mean?

中文解析:

Captured environment 指闭包保留下来的外层变量环境。外层函数结束后，普通局部变量本来应该消失，
但如果内部函数还需要这些变量，Python 会把需要的环境保存下来。

English answer:

A captured environment is the set of outer-scope variables that a closure keeps access to.
The function object can use those variables later because Python preserves the environment
needed by the function.

Overseas backend interview answer:

I think of the captured environment as configuration or state owned by the returned
function. This is useful for dependency factories, callback factories, and AI prompt
builder functions.

Follow-up questions:

- Does a closure capture all local variables?
- Does Python capture names or values?
- Why does captured mutable state require care?

### Beginner 3. Why can an inner function access variables after the outer function returns?

Question:

Why can this still access `count`?

```python
def make_counter():
    count = 0

    def counter():
        return count

    return counter
```

中文解析:

因为返回的 `counter` 是一个函数对象，而且它需要外层作用域里的 `count`。Python 不会把这个被捕获的
环境销毁，而是把它和函数对象一起保留下来。

English answer:

The inner function can access `count` because it is a closure. Python keeps the captured
environment alive as long as the returned function object needs it.

Overseas backend interview answer:

This behavior lets us build small configured functions, such as a FastAPI dependency
factory or an AI prompt builder, without relying on global variables.

Follow-up questions:

- What happens if two counters are created from two calls?
- Is the outer function still running?
- Where is the state preserved?

### Beginner 4. What does `nonlocal` do?

Question:

What does `nonlocal` do in a closure?

中文解析:

`nonlocal` 告诉 Python：这个名字不是当前内部函数的局部变量，而是来自最近的外层函数作用域。
它用于重新绑定外层函数里的变量。

English answer:

`nonlocal` tells Python to rebind a name in the nearest enclosing function scope instead
of creating a new local variable.

Overseas backend interview answer:

I use `nonlocal` carefully when a closure intentionally owns small internal state, such
as a counter or retry state. I avoid using it for large shared production state because
it can hide mutation.

Follow-up questions:

- Why does mutation sometimes not require `nonlocal`?
- Why does `count = count + 1` fail without `nonlocal`?
- Why is `nonlocal` different from `global`?

### Intermediate 1. Explain closure vs class.

Question:

When would you use a closure instead of a class?

中文解析:

闭包适合捕获少量配置并返回一个主要行为。类适合管理更复杂的状态、多个方法、生命周期和更清晰的对象边界。

English answer:

I use a closure when I need lightweight configured behavior with small captured state.
I use a class when the state is complex, has a lifecycle, or needs multiple methods.

Overseas backend interview answer:

For a simple FastAPI dependency factory, a closure is clean. For a service object that
manages a database client, cache client, retries, and several operations, I would prefer
a class.

Follow-up questions:

- When does a closure become too implicit?
- How would you test closure state?
- How would you refactor a closure into a class?

### Intermediate 2. What is a factory function?

Question:

What is a factory function?

中文解析:

Factory Function 是创建并返回配置好行为的函数。它把配置阶段和业务执行阶段分开。

English answer:

A factory function is a function that creates and returns another object or function,
often with configuration captured in a closure.

Overseas backend interview answer:

Factory functions are useful in backend systems because they separate configuration from
runtime logic. For example, a factory can capture required roles and return a FastAPI
dependency that checks the current user.

Follow-up questions:

- Why does a factory function improve dependency injection?
- What does the returned function capture?
- When would you use a class-based factory instead?

### Intermediate 3. Why is closure useful in backend development?

Question:

Why are closures useful in backend engineering?

中文解析:

闭包可以在不使用全局变量的情况下保存配置和小状态。它常用于依赖工厂、验证器工厂、回调函数、Prompt Builder
和工具注册。

English answer:

Closures are useful because they allow configured behavior without global state. They are
common in dependency injection, callbacks, validators, retry policies, and prompt builders.

Overseas backend interview answer:

In production backend code, closures help keep configuration close to behavior while still
allowing the request-specific data to stay isolated.

Follow-up questions:

- What production risk comes from captured mutable state?
- How can closures help avoid global request state?
- How do closures connect to decorators?

### Intermediate 4. Explain late binding.

Question:

What is late binding in Python closures?

中文解析:

Late Binding 指闭包在调用时查找变量，而不是在创建函数时把值固定下来。

English answer:

Late binding means a closure looks up captured variables when the function is called,
not when the function is created.

Overseas backend interview answer:

Late binding matters when generating callbacks or handlers in a loop. If I do not capture
the current value intentionally, every generated function may use the final loop value.

Follow-up questions:

- Why does late binding happen?
- How does `i=i` fix it?
- Where can this bug appear in backend code?

### Intermediate 5. Why does the famous loop example print `2 2 2`?

Question:

Why does this print `2 2 2`?

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

中文解析:

三个函数捕获的是同一个变量名 `i`，不是每次循环的值。循环结束后，`i` 的最终值是 `2`。
调用函数时才查找 `i`，所以结果都是 `2`。

English answer:

It prints `2 2 2` because all functions capture the same variable `i`. They look up `i`
when called, and after the loop finishes, `i` is `2`.

Overseas backend interview answer:

This is a common callback-generation bug. I fix it by binding the current value explicitly,
for example with `def f(i=i): return i`.

Follow-up questions:

- Does Python capture the variable or the value?
- Why does the default argument fix work?
- How would this affect generated route handlers or job callbacks?

### Senior 1. Explain Python closure from the perspective of function objects.

Question:

Explain closure using Python's object model.

中文解析:

函数本身是对象。闭包就是一个函数对象携带了它执行时还需要的外层环境。这个函数对象可以被赋值、返回、传递，
并在未来继续使用捕获的环境。

English answer:

From the object model perspective, a closure is a function object that carries references
to variables from its defining environment. The function object can be returned, passed
around, and called later while still using that environment.

Overseas backend interview answer:

This explains why frameworks can accept callables and why factories can return configured
functions. The callable is an object, and its captured environment carries the configuration.

Follow-up questions:

- What makes a function first-class?
- How does this connect to dependency injection?
- What can go wrong if the captured environment is mutable?

### Senior 2. Explain how closure works internally.

Question:

How does a closure work internally?

中文解析:

当内部函数引用外层变量，并且内部函数会在外层函数结束后继续存在时，Python 会保留这些被引用的变量。
返回的函数对象持有对这些变量环境的引用。

English answer:

Python preserves the variables needed by the inner function and attaches that environment
to the returned function object. The outer function does not keep running, but the captured
environment remains alive.

Overseas backend interview answer:

This means closure state has a lifecycle. If the closure is kept globally or reused across
workers, its captured state can live much longer than expected, so ownership must be clear.

Follow-up questions:

- Does the outer stack frame keep running?
- Why can captured state outlive the function call?
- How would you inspect closure behavior during debugging?

### Senior 3. Why does Python capture names instead of values?

Question:

Why does Python capture names instead of values?

中文解析:

Python 的作用域规则基于名字查找。闭包保存的是变量环境，调用时再解析名字。这让闭包可以保存可变状态，
也能让 `nonlocal` 更新外层变量，但副作用是会出现 Late Binding。

English answer:

Python closures capture variables by reference to the environment, so names are resolved
when the function is called. This supports state preservation and `nonlocal`, but it also
creates late binding behavior.

Overseas backend interview answer:

The trade-off is flexibility versus surprise. I use explicit binding, such as default
arguments, when generating functions in loops so the production behavior is predictable.

Follow-up questions:

- What is the trade-off of this design?
- Why does late binding surprise new engineers?
- How would you make the behavior explicit?

### Senior 4. Explain Dependency Factory in FastAPI.

Question:

How does a closure support a FastAPI dependency factory?

中文解析:

FastAPI 的 `Depends()` 接收 callable。Factory Function 可以先捕获配置，比如 required role，
然后返回真正处理请求的依赖函数。

English answer:

A FastAPI dependency factory captures configuration and returns a dependency function.
The returned callable is used by `Depends()` during the request lifecycle.

Overseas backend interview answer:

For example, `require_role("admin")` can return a dependency that checks the current user.
The role is configuration captured by the closure; the user remains request-scoped data.

Follow-up questions:

- Why should the current user not be captured globally?
- What should be captured by the factory?
- What should remain request-scoped?

### Senior 5. Explain Prompt Factory in AI Backend.

Question:

How can closures support AI prompt builders?

中文解析:

Prompt Factory 可以捕获固定配置，比如产品名、语气、系统规则，然后返回一个函数，根据用户输入生成 prompt。
这样配置和运行时消息可以分离。

English answer:

A prompt factory can capture stable configuration such as product name, tone, or system
rules, and return a builder function that creates prompts from request-specific input.

Overseas backend interview answer:

This pattern helps avoid global prompt state and prevents different users' messages from
mixing. Stable configuration is captured; conversation history should remain session-scoped.

Follow-up questions:

- What should not be captured in a global prompt builder?
- How can shared `messages` cause prompt pollution?
- When would you store prompt configuration in a class instead?

### Senior 6. Explain trade-offs between Closure and OOP.

Question:

What are the trade-offs between closure-based design and object-oriented design?

中文解析:

闭包轻量，适合少量配置和一个主要行为；OOP 更显式，适合复杂状态、多方法、生命周期和团队协作。

English answer:

Closures are lightweight and good for small configured behavior. Classes are more explicit
and better for complex state, multiple methods, lifecycle management, and large-team
maintainability.

Overseas backend interview answer:

I choose the simplest structure that makes ownership clear. For a small dependency factory,
I use a closure. For a production service with database access, retries, logging, and
several operations, I use a class.

Follow-up questions:

- How do you avoid overusing closures?
- What would a tech lead reject in a closure-heavy design?
- How do testing and observability affect the choice?

---

## Day06 Questions: Decorators

### Beginner 1. What is a decorator?

Question:

What is a decorator in Python?

中文解释:

Decorator 是一个接收函数并返回函数的函数。它通常用于在不修改业务函数代码的情况下，为函数增加日志、
计时、认证、缓存、重试等通用能力。

English answer:

A decorator is a function that takes another function and returns a new function, usually
to add reusable behavior around the original function.

Overseas interview answer:

In backend systems, I use decorators for cross-cutting concerns such as logging, timing,
authentication, retry, cache, and tracing, so the business function stays focused.

### Beginner 2. How does `@decorator` work?

Question:

How does `@decorator` work internally?

中文解释:

`@decorator` 是语法糖。它等价于 `func = decorator(func)`。Python 先创建原始函数对象，
然后把这个函数传给 decorator，再把函数名绑定到 decorator 返回的新函数。

English answer:

`@decorator` is equivalent to `func = decorator(func)`. Python passes the original function
object to the decorator and rebinds the function name to the returned callable.

Overseas interview answer:

This mental model helps me debug decorators because I know the function name usually points
to the wrapper after decoration.

### Beginner 3. What is wrapper?

Question:

What is the wrapper function in a decorator?

中文解释:

wrapper 是 decorator 返回的函数。函数被装饰后，调用函数名时真正先执行的是 wrapper。wrapper 通常会
在调用原始函数前后添加额外逻辑。

English answer:

The wrapper is the returned function that actually runs when the decorated function is
called. It usually executes logic before and after calling the original function.

Overseas interview answer:

The wrapper is where I add infrastructure behavior such as logging, timing, retry, or
request tracing while preserving the original business function.

### Beginner 4. Why use decorators?

Question:

Why do we use decorators?

中文解释:

Decorator 用于抽离横切关注点，避免在每个业务函数里重复写相同的日志、计时、权限、缓存或 tracing 逻辑。

English answer:

We use decorators to avoid duplicated infrastructure code and to apply consistent behavior
across many functions without modifying the business logic.

Overseas interview answer:

Decorators improve maintainability because one tested wrapper can enforce the same logging,
timing, or authorization policy across many backend functions.

### Intermediate 1. Why do decorators usually use `*args` and `**kwargs`?

Question:

Why do production decorators usually define `wrapper(*args, **kwargs)`?

中文解释:

因为不同函数的参数不同。`*args` 接收位置参数，`**kwargs` 接收关键字参数。这样 wrapper 可以把参数
原样透传给原始函数。

English answer:

Decorators usually use `*args` and `**kwargs` so the wrapper can accept and forward any
positional and keyword arguments to the original function.

Overseas interview answer:

This makes the decorator reusable across many function signatures. Without it, decorated
functions can fail with `TypeError`.

### Intermediate 2. What does `functools.wraps` do?

Question:

What does `functools.wraps` do?

中文解释:

`functools.wraps` 用来保留原始函数的元数据，例如 `__name__`、`__doc__`、`__annotations__`
以及 signature 相关信息。

English answer:

`functools.wraps` preserves metadata from the original function, including the name,
docstring, annotations, and signature-related information.

Overseas interview answer:

This matters in production because logs, debugging tools, documentation generators, and
frameworks like FastAPI rely on accurate function metadata.

### Intermediate 3. Why does `@decorator` equal `func = decorator(func)`?

Question:

Why is `@decorator` equivalent to `func = decorator(func)`?

中文解释:

因为 decorator 语法本质上就是函数对象重绑定。原始函数先被创建，然后传入 decorator，最后函数名绑定到
decorator 返回的对象。

English answer:

Decorator syntax is syntactic sugar. Python creates the function object, passes it to the
decorator, and assigns the returned callable back to the original function name.

Overseas interview answer:

This explains why the wrapper becomes the callable and why missing metadata preservation
can make logs show `wrapper` instead of the original function name.

### Intermediate 4. Why does wrapper become the callable function?

Question:

Why does the wrapper function become the callable function?

中文解释:

因为 decorator 返回的是 wrapper，并且函数名被重新绑定到 wrapper。所以后续调用函数名时，实际调用的是
wrapper。

English answer:

The wrapper becomes the callable because the decorator returns it, and Python rebinds the
original function name to that returned wrapper.

Overseas interview answer:

This is why wrapper design is important. If the wrapper forgets arguments, return values,
metadata, or async behavior, the decorated function's production behavior changes.

### Senior 1. Explain the implementation of Python decorators.

Question:

Explain how Python decorators are implemented.

中文解释:

Decorator 是高阶函数。它接收函数对象，在内部定义 wrapper，wrapper 通过闭包捕获原始函数，然后 decorator
返回 wrapper。调用被装饰函数时，实际先调用 wrapper。

English answer:

Decorators are higher-order functions. They receive a function object, define an inner
wrapper that captures the original function, and return that wrapper.

Overseas interview answer:

From an engineering perspective, decorators combine function objects and closures to add
reusable behavior around business functions.

### Senior 2. Explain metadata preservation.

Question:

What is metadata preservation and why does it matter?

中文解释:

Metadata preservation 指装饰后仍然保留原始函数的名称、文档、类型注解和签名信息。没有它，日志可能全部显示
`wrapper`，框架也可能无法正确反射函数。

English answer:

Metadata preservation means keeping the original function's name, docstring, annotations,
and signature information after decoration.

Overseas interview answer:

It matters because production debugging, API documentation, tracing, and framework
reflection depend on accurate metadata.

### Senior 3. Why does FastAPI rely heavily on decorators?

Question:

Why does FastAPI rely heavily on decorators?

中文解释:

FastAPI 使用 decorators 注册路由，并将 HTTP 方法、路径、函数签名、参数类型和文档信息连接起来。

English answer:

FastAPI uses decorators to register route handlers and keep route metadata close to the
handler function. It also inspects annotations and signatures for validation and OpenAPI
generation.

Overseas interview answer:

This is why custom decorators around FastAPI endpoints must preserve metadata with
`functools.wraps` and handle async functions correctly.

### Senior 4. How do decorators improve maintainability in backend systems?

Question:

How do decorators improve maintainability?

中文解释:

Decorators 把重复的横切关注点集中到一个地方，避免每个业务函数都重复实现日志、计时、认证、缓存和重试逻辑。

English answer:

Decorators improve maintainability by centralizing cross-cutting concerns and applying
them consistently across many functions.

Overseas interview answer:

They reduce duplication, make code review easier, and allow teams to change infrastructure
behavior in one place instead of editing every business function.

### Senior 5. Explain real production use cases of decorators in AI Backend.

Question:

What are real decorator use cases in AI backend systems?

中文解释:

AI Backend 中 Decorator 可用于模型调用耗时统计、token 记录、request tracing、tool call tracing、
cache、retry 和权限控制。

English answer:

In AI backends, decorators can track latency, token usage, model calls, tool calls, cache
hits, retries, and request IDs.

Overseas interview answer:

I would use decorators for AI observability, but I would avoid logging raw prompts or user
messages because they may contain sensitive data.

### Senior 6. Why are cross-cutting concerns implemented using decorators?

Question:

Why are decorators a good fit for cross-cutting concerns?

中文解释:

横切关注点影响很多函数，但不是这些函数的核心业务逻辑。Decorator 可以在函数外层统一添加这些能力。

English answer:

Cross-cutting concerns affect many functions but are not the core business logic of those
functions. Decorators let us apply those concerns consistently around the functions.

Overseas interview answer:

For example, logging and tracing should be consistent across the system, but they should
not make every service function harder to read.

---

## Day07 Questions: Iterators & Generators

### Beginner 1. What is an iterable?

Question:

What is an iterable in Python?

Standard Answer:

An iterable is an object that can produce an iterator, usually by being passed to `iter()`.

Follow-up Questions:

- Is a list iterable?
- Can an iterable create more than one iterator?

Engineering Perspective:

An iterable represents a data source that can be traversed. In backend systems, that data
source may be rows, files, API pages, browser results, or stream chunks.

### Beginner 2. What is an iterator?

Question:

What is an iterator?

Standard Answer:

An iterator is an object that returns values one at a time with `next()` and remembers its
current position.

Follow-up Questions:

- What happens when an iterator is exhausted?
- Why can sharing one iterator be risky?

Engineering Perspective:

Iterators carry traversal state. If two parts of a system consume the same iterator, they
can affect each other.

### Beginner 3. What does `iter()` do?

Question:

What does `iter()` do?

Standard Answer:

`iter()` asks an iterable for an iterator.

Follow-up Questions:

- What does a `for` loop do internally?
- What happens if an object is not iterable?

Engineering Perspective:

`iter()` is the entry point into Python's iteration protocol.

### Beginner 4. What does `next()` do?

Question:

What does `next()` do?

Standard Answer:

`next()` asks an iterator for the next value.

Follow-up Questions:

- What happens when there are no more values?
- Why does Python not return `None`?

Engineering Perspective:

`next()` is pull-based data flow. The consumer asks for one more item when it is ready.

### Beginner 5. What is `StopIteration`?

Question:

What is `StopIteration`?

Standard Answer:

`StopIteration` is the signal that an iterator has no more values.

Follow-up Questions:

- Is `StopIteration` always a bug?
- Who catches it in a `for` loop?

Engineering Perspective:

In the iterator protocol, `StopIteration` is normal control flow, not a production crash.

### Beginner 6. What is a generator?

Question:

What is a generator?

Standard Answer:

A generator is an iterator created by a function that uses `yield`.

Follow-up Questions:

- Does calling a generator function run the body immediately?
- What does `yield` do?

Engineering Perspective:

Generators are useful because they model pausable and resumable data flow.

### Beginner 7. What is the difference between `yield` and `return`?

Question:

What is the difference between `yield` and `return`?

Standard Answer:

`return` ends a function. `yield` produces a value and pauses the function so it can resume
later.

Follow-up Questions:

- Can a generator yield multiple values?
- What happens when a generator reaches the end?

Engineering Perspective:

`yield` supports incremental output, which is essential for streaming and pipeline systems.

### Intermediate 1. Why are iterable and iterator separated?

Question:

Why does Python separate iterable and iterator?

Standard Answer:

Python separates them so reusable data containers can produce independent iterator objects
while each iterator owns its traversal state.

Follow-up Questions:

- Why can a list be looped over multiple times?
- Why is a generator usually one-time use?

Engineering Perspective:

This design prevents reusable containers from mixing data ownership with traversal state.

### Intermediate 2. Why does Python not return `None` instead of `StopIteration`?

Question:

Why does Python raise `StopIteration` instead of returning `None`?

Standard Answer:

Because `None` can be a valid value. `StopIteration` separates end-of-iteration control
flow from real data.

Follow-up Questions:

- Can an iterator yield `None`?
- What ambiguity would `None` create?

Engineering Perspective:

The protocol avoids ambiguous sentinel values and keeps streaming data safe.

### Intermediate 3. Why can a generator only be consumed once?

Question:

Why can a generator only be consumed once?

Standard Answer:

A generator is its own iterator. It stores its execution state, and after it reaches the
end, it is exhausted.

Follow-up Questions:

- How do you iterate again?
- How can logging accidentally consume a generator?

Engineering Perspective:

Treat generators as one-pass streams. If the caller needs reuse, return a list or create a
new generator.

### Intermediate 4. Generator Expression vs List Comprehension

Question:

What is the difference between a generator expression and a list comprehension?

Standard Answer:

A list comprehension builds all values immediately. A generator expression produces values
lazily when requested.

Follow-up Questions:

- Which supports indexing?
- Which is better for streaming?

Engineering Perspective:

Use lists for reusable in-memory results. Use generator expressions for one-pass lazy
processing.

### Intermediate 5. What is lazy evaluation?

Question:

What is lazy evaluation?

Standard Answer:

Lazy evaluation means computation happens only when a value is requested.

Follow-up Questions:

- How does lazy evaluation affect memory?
- How does it affect time-to-first-result?

Engineering Perspective:

Lazy evaluation improves streaming behavior and pipeline design, not only memory usage.

### Senior 1. Explain Python Generator Protocol.

Question:

Explain Python generator protocol.

Standard Answer:

A generator follows the iterator protocol. It produces values with `yield`, resumes on
`next()`, and signals completion with `StopIteration`.

Follow-up Questions:

- What state does a generator preserve?
- How does a `for` loop consume a generator?

Engineering Perspective:

The protocol gives Python one model for lists, files, streams, generated values, and
pipeline outputs.

### Senior 2. Explain Generator Lifecycle.

Question:

Explain the lifecycle of a generator.

Standard Answer:

A generator is created, starts running when consumed, pauses at each `yield`, resumes on
the next request, and eventually becomes exhausted.

Follow-up Questions:

- Does calling the generator function execute the body?
- What happens after exhaustion?

Engineering Perspective:

Generator lifecycle matters for resource cleanup, streaming errors, and one-time data
ownership.

### Senior 3. Why does FastAPI `StreamingResponse` use generators?

Question:

Why does FastAPI `StreamingResponse` use generators?

Standard Answer:

`StreamingResponse` can consume a generator and send chunks as they are produced instead
of building the entire response first.

Follow-up Questions:

- What happens if the generator fails midway?
- Why does this improve time-to-first-byte?

Engineering Perspective:

Generators support HTTP streaming, large responses, and real-time output.

### Senior 4. Explain generator-based streaming in AI Backend.

Question:

How do generators connect to AI backend streaming?

Standard Answer:

An AI backend can yield token chunks as the model produces them, letting the frontend show
output incrementally.

Follow-up Questions:

- Why does ChatGPT appear to type in real time?
- What should be tracked during token streaming?

Engineering Perspective:

Token streaming is a pausable data-flow model that improves perceived latency and user
experience.

### Senior 5. Explain Pipeline vs Batch processing.

Question:

Explain pipeline vs batch processing.

Standard Answer:

Batch processing collects all data before processing or returning it. Pipeline processing
passes items through stages as soon as they become available.

Follow-up Questions:

- Which design has faster first output?
- Which design is easier to replay?

Engineering Perspective:

Pipeline design scales better for large or streaming data, but it requires careful handling
of one-time consumption and partial failures.

### Senior 6. How does generator design improve scalability?

Question:

How does generator design improve scalability?

Standard Answer:

Generators improve scalability by producing data incrementally, reducing peak memory,
supporting streaming output, and enabling pipeline processing.

Follow-up Questions:

- Is memory saving the only benefit?
- What risks come with generator-based design?

Engineering Perspective:

The deeper scalability benefit is controlled data flow: the system can process one item or
chunk at a time.

### Senior 7. What production bugs can happen when a generator is accidentally consumed?

Question:

What production bugs can happen when a generator is accidentally consumed?

Standard Answer:

A generator is one-pass. If code converts it to a list, sums it, logs it, or iterates over
it for debugging, the generator may be exhausted before the real consumer uses it.

Follow-up Questions:

- Why does `list(generator)` consume the generator?
- Why can `sum(generator)` return a value the first time and `0` the second time?
- How can this break FastAPI `StreamingResponse`?
- How can this break LLM token streaming?

Engineering Perspective:

This is a production ownership bug. A stream should have one clear consumer. Debugging code
should not steal values from the real response sender, pipeline writer, or token streamer.

Example:

```python
stream = llm.stream(prompt)

print(list(stream))  # consumes stream

for token in stream:
    send(token)      # sends nothing
```

### Senior 8. Explain "data can be shared, state should not be shared."

Question:

Explain the engineering principle "data can be shared, state should not be shared."

Standard Answer:

An iterable can safely hold shared data, while each iterator should own independent
traversal state. Sharing traversal state causes consumers to affect each other.

Follow-up Questions:

- Why is a list iterable but not an iterator?
- What would happen if the list stored `current_index` itself?
- How does this connect to FastAPI request state?
- How does this connect to Playwright `BrowserContext` isolation?
- How does this connect to AI token streams?

Engineering Perspective:

The same principle appears across backend systems: requests need isolated state, Playwright
jobs need isolated browser contexts, and each LLM stream needs its own token stream state.

---

## Day08 Questions: Exception Handling

### Beginner 1. What is exception handling in Python?

Question:

What is exception handling in Python?

Standard Answer:

Exception handling is Python's mechanism for responding to errors or exceptional conditions
using `try`, `except`, and `raise`.

Engineering Perspective:

In backend systems, exception handling defines where failures are detected, logged,
translated, retried, or returned to users.

### Beginner 2. What is the difference between `try/except` and normal control flow?

Question:

What is the difference between `try/except` and normal control flow?

Standard Answer:

Normal control flow handles expected branches. `try/except` handles failures that interrupt
normal execution.

Engineering Perspective:

Return values are good for expected outcomes. Exceptions are better for invalid operations,
failed dependencies, and broken assumptions.

### Beginner 3. Why should we catch specific exceptions instead of using `except Exception`?

Question:

Why should we catch specific exceptions instead of using `except Exception`?

Standard Answer:

Specific exceptions preserve error meaning and avoid hiding unexpected bugs.

Engineering Perspective:

In production, broad catches can turn real bugs into silent `None` values or misleading
fallback behavior. Catch `Exception` only at clear boundaries where you can log, clean up,
or translate the failure.

### Intermediate 1. What is exception propagation?

Question:

What is exception propagation?

Standard Answer:

Exception propagation means an exception moves up the call stack until some caller handles
it or the framework reports it.

Engineering Perspective:

Propagation lets low-level code detect failure while higher-level boundaries decide whether
to retry, log, convert to HTTP, or fail the job.

### Intermediate 2. What happens when an exception is raised inside a nested function call?

Question:

What happens when an exception is raised inside a nested function call?

Standard Answer:

If the nested function does not catch the exception, it propagates to its caller, then to
the caller's caller, and continues upward.

Engineering Perspective:

This allows service code to stay focused while API or worker boundaries handle response
translation and observability.

### Intermediate 3. What is the difference between returning `None` and raising an exception?

Question:

What is the difference between returning `None` and raising an exception?

Standard Answer:

Returning `None` can represent expected absence. Raising an exception represents an invalid
operation, failed dependency, or broken invariant.

Engineering Perspective:

If the caller can safely continue, `None` may be acceptable. If normal execution should
stop, raise a clear exception.

### Intermediate 4. Why should validation logic raise `ValueError` or custom exceptions?

Question:

Why should validation logic raise `ValueError` or custom exceptions?

Standard Answer:

Validation failures mean input violates required rules. Raising `ValueError` or a custom
exception makes the failure explicit.

Engineering Perspective:

In AI backends, an `InvalidPromptError` can become a clean user-facing 400 response, while
LLM provider failures can be handled differently.

### Senior 1. How would you design exception handling in a production FastAPI service?

Question:

How would you design exception handling in a production FastAPI service?

Standard Answer:

I would raise domain-specific exceptions in service code, translate them into
`HTTPException` or registered exception handlers at the API boundary, log root causes
internally, and avoid exposing internal tracebacks to users.

Engineering Perspective:

This keeps business logic independent from HTTP while still giving clients correct status
codes and useful error messages.

### Senior 2. How does exception propagation support framework-level error handling?

Question:

How does exception propagation support framework-level error handling?

Standard Answer:

Propagation lets exceptions travel from lower-level code to framework boundaries, where
they can be converted into standardized HTTP responses, task failures, or logs.

Engineering Perspective:

This avoids duplicating error conversion logic in every function and keeps error handling
consistent across the service.

### Senior 3. Why are custom exceptions useful in large backend systems?

Question:

Why are custom exceptions useful in large backend systems?

Standard Answer:

Custom exceptions encode domain meaning and allow different failure categories to be
handled differently.

Engineering Perspective:

`InvalidPromptError`, `LLMRequestError`, `ToolExecutionError`, and `RateLimitError` should
not all have the same retry, logging, or user-response behavior.

### Senior 4. What problem does `raise ... from ...` solve?

Question:

What problem does `raise ... from ...` solve?

Standard Answer:

It preserves the original exception as the cause when translating a low-level error into a
higher-level domain exception.

Engineering Perspective:

It supports root cause analysis. The application can expose a domain error while logs and
tracebacks still show the original provider timeout, parsing error, or tool failure.

### Senior 5. How would you handle LLM API failures in an AI Backend system?

Question:

How would you handle LLM API failures in an AI Backend system?

Standard Answer:

I would classify failures such as prompt validation errors, rate limits, timeouts, provider
errors, and tool execution failures. I would retry safe transient failures, preserve root
cause, log structured context, and return appropriate user-facing responses.

Engineering Perspective:

Do not collapse all LLM failures into `None` or generic 500 errors. The error type should
guide retry policy, user messaging, alerting, and agent state updates.

### Senior 6. How should Playwright automation workers handle recoverable vs non-recoverable errors?

Question:

How should Playwright automation workers handle recoverable vs non-recoverable errors?

Standard Answer:

Recoverable errors such as temporary timeouts can be retried with limits. Non-recoverable
errors such as invalid credentials or missing required state should fail the job clearly.

Engineering Perspective:

Workers should capture evidence such as screenshots, clean up browser contexts, preserve
root cause, and avoid infinite retries or silent `pass` blocks.

### Senior 7. How would you design exception handling for a full AI Backend system?

Question:

How would you design exception handling for an AI Backend system that uses FastAPI,
background workers, Playwright tools, and LLM providers?

Standard Answer:

I would define domain exceptions such as `InvalidPromptError`, `LLMRequestError`,
`ToolExecutionError`, and `RateLimitError`. At the FastAPI API boundary, I would translate
domain exceptions into safe HTTP responses. At the worker boundary, I would separate retryable
failures from fail-fast failures. For Playwright tools, I would capture evidence such as
screenshots before cleanup. For LLM providers, I would classify rate limits, timeouts, and
provider errors separately. I would use structured logging and preserve root cause with
`raise ... from ...`, while ensuring user-facing messages do not leak internal tracebacks.

Engineering Perspective:

The important design is not "catch everything." The important design is clear failure
ownership. API boundaries translate errors for users, worker boundaries decide retry vs
fail-fast, tool boundaries capture evidence, and provider boundaries preserve root cause
for debugging.

---

## Day09 Questions: Modules and Packages

### Beginner 1. What is a Python module?

Question:

What is a Python module?

Standard Answer:

A Python module is a file that Python loads as a runtime module object. The module object
has its own namespace containing names such as functions, classes, constants, and imported
objects.

Engineering Perspective:

In backend systems, modules are the first unit of code organization. A module should have a
clear responsibility and should be safe to import during tests, application startup, and
worker boot.

### Beginner 2. What is a package?

Question:

What is a package?

Standard Answer:

A package is a directory that groups related modules and subpackages under one namespace.

Engineering Perspective:

Packages help large codebases express architecture boundaries, such as API routes,
services, repositories, schemas, tools, and provider clients.

### Beginner 3. What does `__init__.py` do?

Question:

What does `__init__.py` do?

Standard Answer:

`__init__.py` marks a directory as a regular Python package and can define package-level
initialization or re-export selected names.

Engineering Perspective:

I keep `__init__.py` lightweight because it runs when the package is imported. Heavy work
there can create hidden startup side effects.

### Beginner 4. What is the difference between `import module` and `from module import function`?

Question:

What is the difference between `import module` and `from module import function`?

Standard Answer:

Both load the module, but they bind different names in the current namespace. `import
module` binds the module object. `from module import function` binds the imported function
directly.

Engineering Perspective:

`import module` keeps ownership visible through the module namespace. `from module import
function` is concise when the imported name is specific and clear.

### Intermediate 1. Explain Python import execution.

Question:

Explain Python import execution.

Standard Answer:

Python checks `sys.modules` first. If the module is already loaded, Python reuses the cached
module object. If not, Python finds the module, creates a module object, stores it in
`sys.modules`, executes the module's top-level code, and binds the requested name.

Engineering Perspective:

Import is execution, not copy-paste. This is why top-level database connections, browser
launches, or LLM calls during import are risky.

Follow-up Questions:

- Why does top-level code run during import?
- Why does Python cache modules?
- What happens if import-time code raises an exception?

### Intermediate 2. Why is a module executed only once?

Question:

Why is a module executed only once?

Standard Answer:

After the first successful import, Python stores the module object in `sys.modules`. Later
imports reuse the same cached module object instead of executing the source file again.

Engineering Perspective:

This preserves module identity and avoids repeated top-level execution. The trade-off is
that module-level mutable state is shared by every importer.

Follow-up Questions:

- How can module caching create hidden shared state?
- Why should AI conversation state not live in a module-level list?

### Intermediate 3. What is `sys.modules`?

Question:

What is `sys.modules`?

Standard Answer:

`sys.modules` is a dictionary mapping module names to loaded module objects.

Engineering Perspective:

It is the module cache. Understanding it helps explain why repeated imports do not
re-execute modules and why module-level mutable state can be shared across the application.

### Intermediate 4. Difference between absolute and relative imports.

Question:

What is the difference between absolute and relative imports?

Standard Answer:

An absolute import uses the full package path, such as `from app.services.user_service
import create_user`. A relative import uses the current package position, such as `from
.user_service import create_user`.

Engineering Perspective:

Absolute imports are usually clearer in large backend systems because they show ownership
and package boundaries directly. Simple relative imports can be acceptable inside small
local packages.

### Intermediate 5. What are import side effects?

Question:

What are import side effects?

Standard Answer:

Import side effects are meaningful actions that happen just because a module is imported,
such as connecting to a database, launching a browser, registering tools, or calling an
external API.

Engineering Perspective:

Import side effects make startup, tests, workers, and debugging unpredictable. Production
modules should usually define functions, classes, constants, and factories at import time,
then perform runtime work explicitly.

### Senior 1. Explain Python's import mechanism.

Question:

Explain Python's import mechanism.

Standard Answer:

Python resolves the requested module name, checks `sys.modules`, creates a module object if
needed, stores it in the cache, executes top-level code to populate the module namespace,
and binds a name in the importing module. Later imports reuse the cached module object.

Engineering Perspective:

The import mechanism affects architecture. Clean imports make application startup
predictable, reduce circular dependencies, and keep package boundaries understandable.

### Senior 2. How does Python cache imported modules?

Question:

How does Python cache imported modules?

Standard Answer:

Python stores loaded module objects in `sys.modules`, keyed by module name. When the same
module is imported again, Python returns the cached object instead of executing the module
again.

Engineering Perspective:

Caching improves performance and preserves module identity, but it also means module-level
mutable objects are shared globally.

### Senior 3. Why are absolute imports preferred in large backend systems?

Question:

Why are absolute imports preferred in large backend systems?

Standard Answer:

Absolute imports make the source package explicit. They improve readability, code review,
tooling, and refactoring in large codebases.

Engineering Perspective:

When a service grows, import clarity becomes architecture clarity. Engineers should not
need to count dots or guess where a dependency comes from.

### Senior 4. What problems can namespace pollution cause?

Question:

What problems can namespace pollution cause?

Standard Answer:

Namespace pollution can cause name collisions, accidental shadowing, hidden dependencies,
and unclear ownership. Wildcard imports are a common source of namespace pollution.

Engineering Perspective:

In production code, explicit imports make dependencies reviewable and reduce the chance of
accidental behavior changes when another module adds a new public name.

### Senior 5. How should packages be organized in a FastAPI project?

Question:

How should packages be organized in a FastAPI project?

Standard Answer:

I would separate route handlers, services, repositories, schemas, dependencies,
configuration, and domain errors. Route modules can import services, services can import
repositories, but lower-level modules should not depend on HTTP route modules.

Engineering Perspective:

Package structure should reflect dependency direction and lifecycle ownership. Request
state should be created during the request lifecycle, not at import time.

### Senior 6. How do module boundaries affect AI Backend architecture?

Question:

How do module boundaries affect AI Backend architecture?

Standard Answer:

AI backend modules should separate prompts, tools, LLM clients, agent orchestration,
session state, and domain errors. Clear boundaries make testing, retry logic, observability,
and provider replacement easier.

Engineering Perspective:

If prompts, tools, provider calls, and session state are mixed together, the system becomes
hard to test and easy to pollute with shared state. Import-time tool registration should be
intentional, not accidental.

---

## Day10 Questions: Type Hints

### Beginner 1. Why did Python introduce Type Hints?

Question:

Why did Python introduce Type Hints?

中文解析:

Python 仍然是动态语言。Type Hints 的目标不是把 Python 变成强制静态类型语言，而是让函数边界更清楚，让人、IDE、静态检查工具、框架和 AI 助手都能理解代码契约。

Standard Answer:

Python introduced Type Hints to improve readability, tooling, static analysis, refactoring,
framework integration, and maintainability while keeping Python dynamically typed.

### Beginner 2. Are Type Hints checked at runtime?

Question:

Are Type Hints checked at runtime by default?

中文解析:

默认不会。Type Hints 描述预期类型，但 Python 不会自动在函数调用前检查。FastAPI 和 Pydantic 这类框架可以读取 Type Hints 并执行运行时校验。

Standard Answer:

No. Type Hints are not enforced at runtime by default. They are mainly used by humans,
IDEs, static type checkers, and frameworks. Frameworks such as FastAPI and Pydantic can use
them for runtime validation.

### Beginner 3. Why should parameters be annotated?

Question:

Why should function parameters be annotated?

中文解析:

参数类型提示告诉调用者应该传什么，也告诉 IDE 和静态检查工具这个函数的输入契约。

Standard Answer:

Parameter annotations define what callers are expected to pass. They make the function
interface easier to understand and safer to use.

### Beginner 4. Why should return values be annotated?

Question:

Why should return values be annotated?

中文解析:

返回值是调用方继续工作的基础。如果返回类型不清楚，后续代码就只能猜。

Standard Answer:

Return annotations tell callers what to expect from a function. They reduce guessing and
make downstream code easier to review and refactor.

### Beginner 5. What is the difference between `list[T]` and `list`?

Question:

What is the difference between `list[T]` and `list`?

中文解析:

`list` 只说明这是列表，`list[T]` 说明列表里的元素类型。后者对工程更有价值。

Standard Answer:

`list` only says the value is a list. `list[T]` also tells us the type of each item in the
list.

### Intermediate 1. What is the difference between `Optional` and `Union`?

Question:

What is the difference between `Optional` and `Union`?

中文解析:

`Optional[User]` 本质上是 `Union[User, None]`。它专门表达“这个值可能不存在”。

Standard Answer:

`Optional[T]` means `T | None`. `Union` is more general and represents a value that may be
one of several types.

Follow-up Question:

When should you avoid large unions?

### Intermediate 2. What is the difference between `User | None` and `Optional[User]`?

Question:

What is the difference between `User | None` and `Optional[User]`?

中文解析:

语义相同，`User | None` 是现代 Python 更直接的写法。

Standard Answer:

They mean the same thing: the value can be a `User` or `None`. `User | None` is the modern
syntax.

### Intermediate 3. Why is `list[User]` better than `list`?

Question:

Why is `list[User]` better than `list`?

中文解析:

因为它保留了元素类型。调用者、IDE 和静态检查工具都知道列表里的每一项应该是 `User`。

Standard Answer:

`list[User]` preserves the item type. It tells readers and tools that every item should be
a `User`, which improves autocomplete and static checking.

### Intermediate 4. Why is a Type Hint an interface contract?

Question:

Why is a Type Hint an interface contract?

中文解析:

Type Hint 说明函数承诺接收什么、返回什么。它不是实现细节，而是调用方依赖的边界协议。

Standard Answer:

A Type Hint is an interface contract because it describes what a function accepts and
returns. It defines expectations between caller and implementation.

Follow-up Question:

How does this contract help during refactoring?

### Intermediate 5. What is Type Inference?

Question:

What is Type Inference?

中文解析:

Type Inference 是工具根据上下文推断变量类型，不需要每个局部变量都显式标注。

Standard Answer:

Type inference means a tool can infer a variable's type from context without an explicit
annotation.

### Intermediate 6. Why can IDEs autocomplete better with Type Hints?

Question:

Why can IDEs autocomplete better with Type Hints?

中文解析:

IDE 知道变量是什么类型，就能知道它有哪些属性和方法。

Standard Answer:

Type Hints tell the IDE what type a value has, so the IDE can suggest the correct methods,
attributes, and function signatures.

### Senior 1. Explain Type Hints as interface contracts.

Question:

Explain Type Hints as Interface Contracts.

Standard Answer:

Type Hints define expectations at code boundaries. They describe what a function accepts
and returns, making the contract between caller and implementation explicit.

Interview Review:

Strong answers mention humans, tooling, frameworks, refactoring, and production
maintainability.

Follow-up Questions:

- Are Type Hints runtime checks by default?
- How can frameworks use Type Hints?
- Where should Type Hints be prioritized?

Production Case:

In FastAPI, Type Hints become request models, dependency contracts, response schemas, and
OpenAPI documentation.

### Senior 2. Explain `Generic` and `TypeVar`.

Question:

Explain Generic and TypeVar.

Standard Answer:

`TypeVar` represents a type variable, and `Generic` allows functions or classes to preserve
type relationships across different concrete types.

Interview Review:

The key is relationship preservation, not syntax memorization.

Follow-up Question:

Why is `Response[T]` better than a response wrapper with `data: object`?

Production Case:

An AI backend can use `Response[AgentResult]`, `Response[ToolResult]`, and
`Response[list[ChatMessage]]` while preserving payload type.

### Senior 3. Why is `T -> T` better than `object -> object`?

Question:

Why is `T -> T` better than `object -> object`?

Standard Answer:

`object -> object` loses the relationship between input and output. `T -> T` says the
function returns the same type it receives, so type information is preserved.

Interview Review:

This question tests whether the candidate understands generics as contracts, not just
annotations.

Follow-up Question:

How would this affect IDE autocomplete after calling the function?

Production Case:

A generic cache helper can return the same type that was stored instead of forcing callers
to cast from `object`.

### Senior 4. Explain Type Inference.

Question:

Explain Type Inference.

Standard Answer:

Type inference is the ability of tooling to infer a value's type from assignment,
function return values, or control flow without explicit annotations.

Interview Review:

A strong answer explains why obvious local variables often do not need annotations.

Follow-up Question:

When should an empty list still be annotated?

### Senior 5. Why does FastAPI rely heavily on Type Hints?

Question:

Why does FastAPI rely heavily on Type Hints?

Standard Answer:

FastAPI introspects function signatures and Pydantic models. It uses Type Hints for request
parsing, validation, dependency injection, response serialization, and OpenAPI generation.

Interview Review:

Good candidates connect Type Hints to framework behavior, not just readability.

Production Case:

A route parameter annotated as `user_id: int` can be parsed and validated automatically.
A request model annotated with Pydantic fields becomes an OpenAPI schema.

### Senior 6. How do Type Hints improve AI-assisted development?

Question:

How do Type Hints improve AI-assisted development?

Standard Answer:

Type Hints give AI tools clearer context about function contracts, message types, tool
inputs, tool outputs, and generic wrappers. This reduces incorrect assumptions during code
generation.

Interview Review:

This answer is especially important for AI Backend roles.

Follow-up Question:

How would you type an AI tool calling interface?

Production Case:

An AI agent with typed `ChatMessage`, `AgentTask`, `ToolResult`, and `Response[T]` is easier
for both humans and AI assistants to extend safely.

### Senior 7. When should engineers avoid writing Type Hints?

Question:

When should engineers avoid writing Type Hints?

Standard Answer:

Engineers can skip annotations when local variables are obvious and type inference is
clear. Type Hints should reduce ambiguity, not add noise.

Interview Review:

This question tests judgment. Senior engineers do not annotate everything blindly.

Follow-up Question:

Which is more important: typing every local variable or typing public function boundaries?

### Senior 8. How do Type Hints improve maintainability in large backend systems?

Question:

How do Type Hints improve maintainability in large backend systems?

Standard Answer:

They make interfaces explicit, improve refactoring safety, support static analysis,
improve IDE navigation, document expected data shapes, and help frameworks generate
accurate schemas.

Interview Review:

Tie the answer to team scale, onboarding, refactoring, and production risk.

Production Case:

When a service function changes from returning `User` to `User | None`, Type Hints make
callers update missing-case handling instead of failing later in production.

---

# Day11 Object-Oriented Programming

## Day11 Questions: Object-Oriented Programming

### Beginner 1. What is an object?

Question:

What is an object?

中文解析:

对象是运行时存在的值。它有身份、类型、状态和行为。Python 几乎所有东西都是对象。

Standard Answer:

An object is a runtime value with identity, type, state, and behavior.

### Beginner 2. What is a class?

Question:

What is a class?

中文解析:

类是创建实例对象的蓝图。在 Python 中，类本身也是对象。

English Standard Answer:

A class is a blueprint for creating instances. In Python, a class is also an object.

### Beginner 3. What is an instance?

Question:

What is an instance?

中文解析:

实例是由类创建出来的具体对象。实例拥有自己的状态，并可以使用类定义的行为。

English Standard Answer:

An instance is an object created from a class. It owns its own state and can use behavior
defined by the class.

### Beginner 4. Difference between class and instance.

Question:

What is the difference between a class and an instance?

中文解析:

类是创建对象的蓝图，同时在 Python 中类本身也是对象。实例是由类创建出来的具体对象。

Standard Answer:

A class is a blueprint for creating objects and is also an object in Python. An instance is
an object created from a class.

### Beginner 5. What is `self`?

Question:

What is `self`?

中文解析:

`self` 是当前实例对象。调用 `u1.say_hi()` 时，Python 会把 `u1` 作为第一个参数传给方法。

Standard Answer:

`self` is the current instance passed to an instance method. It is a naming convention, not
a Python keyword.

### Beginner 6. State vs Behavior.

Question:

What are state and behavior?

中文解析:

State 是对象拥有的数据，Behavior 是对象通过方法提供的行为。

Standard Answer:

State is the data an object owns. Behavior is what the object can do through methods.

### Beginner 7. Class Attribute vs Instance Attribute.

Question:

What is the difference between a class attribute and an instance attribute?

中文解析:

类属性存在类对象上，可能被多个实例共享。实例属性存在具体实例上，用于保存每个对象自己的状态。

Standard Answer:

A class attribute lives on the class and can be shared by instances. An instance attribute
lives on a specific instance and represents that object's own state.

### Intermediate 1. Explain attribute lookup.

Question:

Explain attribute lookup.

中文解析:

Python 查找属性时，通常先找实例，再找类，再找父类，最后到 `object`。

Standard Answer:

Python looks for an attribute on the instance first, then the class, then parent classes,
and eventually `object`.

Follow-up Question:

Why does `u1.company = "Google"` not modify `User.company`?

### Intermediate 2. Explain method lookup.

Question:

Explain method lookup.

中文解析:

方法也是属性。Python 会按属性查找顺序寻找方法，找到第一个匹配方法后停止。

Standard Answer:

Methods are attributes. Python searches for them using the same lookup order and stops at
the first match.

Follow-up Question:

How does method lookup explain overriding?

### Intermediate 3. Explain inheritance.

Question:

Explain inheritance.

中文解析:

继承表示子类复用和扩展父类行为，适合真实的 Is-A 关系。

Standard Answer:

Inheritance allows a child class to reuse and specialize behavior from a parent class. It
should model a real Is-A relationship.

Follow-up Question:

When is inheritance the wrong tool?

### Intermediate 4. Explain method overriding.

Question:

Explain method overriding.

中文解析:

Override 是子类定义与父类同名的方法，用子类行为替换或扩展父类行为。

Standard Answer:

Method overriding happens when a child class defines a method with the same name as a
parent method, providing more specific behavior.

Follow-up Question:

Why does Python stop lookup after finding the child method?

### Intermediate 5. What does `super()` do?

Question:

What does `super()` do?

中文解析:

`super()` 会按照 MRO 调用下一个类的方法，常用于调用父类初始化逻辑。

Standard Answer:

`super()` delegates method calls to the next class in the Method Resolution Order. It is
commonly used to call parent initialization or behavior.

Follow-up Question:

Why does parent `__init__()` not run automatically?

### Intermediate 6. Why does Python use MRO?

Question:

Why does Python use MRO?

中文解析:

MRO 给方法查找提供确定顺序，尤其在继承链或多继承场景中避免歧义。

Standard Answer:

Python uses MRO to provide a deterministic method lookup order, especially when inheritance
chains become more complex.

Follow-up Question:

Why should backend application code avoid unnecessary complex multiple inheritance?

### Senior 1. Why is composition preferred over inheritance?

Question:

Why is Composition preferred over Inheritance?

Standard Answer:

Composition is preferred when an object uses other objects rather than being a specialized
version of them. It reduces coupling, improves testability, and makes dependencies easier
to replace.

Interview Review:

Strong answers mention Is-A vs Has-A, dependency injection, testability, and object
ownership.

Follow-up Questions:

- When is inheritance still appropriate?
- How does composition help unit testing?

Production Case:

`ChatService` should have `Database`, `RedisCache`, `LLMClient`, `PromptBuilder`, and
`VectorStore` dependencies instead of inheriting from them.

### Senior 2. Explain Is-A vs Has-A.

Question:

Explain Is-A vs Has-A.

Standard Answer:

Is-A usually indicates inheritance. Has-A usually indicates composition.

Interview Review:

The important part is design judgment. `Chromium` is a `Browser`, but `ChatService` has an
`LLMClient`.

Follow-up Question:

How would you model `ChatService` and `LLMClient`?

Production Case:

Using inheritance for Has-A relationships creates confusing APIs and lifecycle ownership.

### Senior 3. How does FastAPI use OOP?

Question:

How does FastAPI use OOP?

Standard Answer:

FastAPI uses objects such as the application object, request object, response object,
dependency objects, and service objects. Even when handlers are functions, the framework
uses objects to manage state and behavior.

Interview Review:

Good answers connect FastAPI OOP to service layers and dependency injection.

Production Case:

A `UserService` can receive a `UserRepository` through composition and be injected into
route handlers.

### Senior 4. How does Playwright use OOP?

Question:

How does Playwright use OOP?

Standard Answer:

Playwright models browser automation with objects such as `Browser`, `BrowserContext`,
`Page`, and `Locator`. Each object owns a different lifecycle responsibility.

Interview Review:

Strong answers mention shared behavior and isolated state.

Production Case:

Workers may share a `Browser`, but each job should usually own its own `BrowserContext` to
avoid cookie and local storage leakage.

### Senior 5. How does AI Backend use composition?

Question:

How does AI Backend use Composition?

Standard Answer:

AI backend services often compose dependencies such as `LLMClient`, `PromptBuilder`,
`VectorStore`, `UserRepository`, `RedisCache`, and database clients so each dependency can
be replaced, tested, and owned explicitly.

Interview Review:

This is a high-value AI Backend answer because it connects OOP with production agent
architecture.

Production Case:

`ChatService` coordinates dependencies but does not inherit from provider, cache, or
database classes.

### Senior 6. Production risks caused by incorrect inheritance.

Question:

What production risks can incorrect inheritance cause?

Standard Answer:

Incorrect inheritance can create hidden coupling, fragile base classes, unclear lifecycle
ownership, unexpected overrides, accidental shared state, and hard-to-test components.

Interview Review:

Strong answers explain concrete failures, not only "inheritance is bad."

Follow-up Question:

How would composition reduce those risks?

### Senior 7. Explain object lifecycle.

Question:

Explain object lifecycle.

Standard Answer:

Object lifecycle describes when an object is created, initialized, used, and released or
cleaned up.

Interview Review:

Connect lifecycle to resources such as database sessions, Playwright contexts, and LLM
clients.

Production Case:

A Playwright job creates a context, uses pages inside it, and closes the context after the
job.

### Senior 8. Explain object ownership.

Question:

Explain object ownership.

Standard Answer:

Object ownership describes which component is responsible for creating, holding, using, and
disposing of an object.

Interview Review:

Object ownership is a senior-level design concept. It prevents hidden shared state and
unclear cleanup responsibility.

Production Case:

In an AI backend, `ChatService` may own request-level orchestration while injected clients
own provider communication, caching, or retrieval behavior.

### Senior 9. How does Dependency Injection relate to OOP?

Question:

How does Dependency Injection relate to OOP?

English Standard Answer:

Dependency Injection is an OOP design technique where an object receives its dependencies
from the outside instead of creating them internally. It supports composition, testability,
and clearer ownership.

Interview Notes:

This answer should connect composition with production testing. A service object should
receive dependencies such as repositories, caches, and clients explicitly.

Production Case:

A `ChatService` can receive `Database`, `RedisCache`, `LLMClient`, `PromptBuilder`, and
`VectorStore` through its constructor. Unit tests can replace those dependencies with
fakes.

---

# Day12 Context Managers

## Day12 Questions: Context Managers

### Beginner 1. What is a Context Manager?

Question:

What is a context manager?

中文解析:

上下文管理器是一个能保证资源被正确释放的对象。它在 `__enter__` 中获取资源，在 `__exit__` 中释放资源，即使中间发生异常也能清理。

Standard Answer:

A context manager is an object that guarantees deterministic cleanup. It acquires a resource
in `__enter__` and releases it in `__exit__`, so cleanup runs even if the body raises.

### Beginner 2. Why use `with`?

Question:

Why use `with`?

中文解析:

`with` 会自动调用 `__enter__` 和 `__exit__`，保证即使函数体抛出异常，清理代码也一定会执行，从而避免资源泄漏。

Standard Answer:

`with` automatically calls `__enter__` and `__exit__`, so cleanup is guaranteed even when the
body raises. It removes manual `close()` calls and prevents resource leaks.

### Beginner 3. What are `__enter__` and `__exit__`?

Question:

What are `__enter__` and `__exit__`?

中文解析:

`__enter__` 负责获取资源，并返回 `as` 绑定的对象。`__exit__` 负责释放资源，并接收异常信息（类型、值、traceback）。

Standard Answer:

`__enter__` acquires the resource and returns what the `as` name points to. `__exit__` runs
afterward to release the resource and receives the exception type, value, and traceback.

### Intermediate 1. Explain the Resource Lifecycle.

Question:

Explain the resource lifecycle.

中文解析:

每个资源都遵循 Acquire -> Use -> Release。最容易出错的是 Release，因为 Use 阶段抛异常时 Release 可能被跳过。上下文管理器保证 Release 一定执行。

Standard Answer:

Every resource follows Acquire, Use, and Release. The dangerous step is Release, because an
exception during Use can skip it. A context manager guarantees Release on every path.

Follow-up Question:

How does `try / finally` express this lifecycle?

### Intermediate 2. `yield` vs `return`.

Question:

What is the difference between `yield` and `return` in a context manager?

中文解析:

`return` 直接结束函数，没有恢复阶段，无法在函数体之后执行清理。`yield` 会暂停函数，把资源交给函数体，之后恢复并执行 `finally` 清理。

Standard Answer:

`return` ends the function with no resume, so there is no place to run cleanup after the body.
`yield` pauses the function, hands the resource to the body, and resumes afterward to run the
`finally` cleanup.

Follow-up Question:

Why must `yield` sit inside `try / finally`?

### Intermediate 3. FastAPI dependency lifecycle.

Question:

Explain the FastAPI dependency lifecycle.

中文解析:

FastAPI 的 `yield` 依赖会在请求前创建资源，`yield` 给处理函数使用，请求结束后恢复生成器并在 `finally` 中关闭资源。会话是请求级别的，一定会被清理。

Standard Answer:

A FastAPI `yield` dependency creates a resource before the request, yields it to the handler,
and resumes after the response to close it in `finally`. The session is request-scoped and
always cleaned up.

Follow-up Question:

Why should the session not be shared across requests?

### Senior 1. How do you guarantee production cleanup?

Question:

How do you guarantee cleanup under failure in production?

中文解析:

用上下文管理器或 `try / finally` 获取每个资源，把释放放进 `finally`，并且不要在 `__exit__` 中返回 `True`，这样错误仍会传播，同时资源一定被释放。

Standard Answer:

I acquire every resource with a context manager or `try / finally`, put release in `finally`,
and avoid returning `True` from `__exit__` so errors still propagate. This guarantees release
on both success and failure paths.

Interview Review:

Strong answers separate the cleanup guarantee from exception propagation.

Follow-up Question:

When would you deliberately suppress an exception in `__exit__`?

Production Case:

A database session dependency must close in `finally`; otherwise a failing query leaks a
connection and eventually exhausts the pool.

### Senior 2. Context managers in FastAPI.

Question:

How do context managers apply to FastAPI?

中文解析:

FastAPI 使用 `yield` 依赖和 `asynccontextmanager` 生命周期处理器，都遵循 Acquire -> Use -> Release，在请求或应用边界保证清理。

Standard Answer:

FastAPI uses `yield` dependencies and `asynccontextmanager` lifespan handlers. Both follow
Acquire -> Use -> Release, with cleanup guaranteed at the request or application boundary.

Interview Review:

Good answers mention request-scoped sessions and application startup/shutdown.

Production Case:

`get_db` yields a session and closes it in `finally` so every request cleans up its own
connection.

### Senior 3. Context managers in Playwright.

Question:

How do context managers apply to Playwright?

中文解析:

Playwright 共享 `Browser`，但每个任务隔离一个 `BrowserContext`，必须在 `finally` 中关闭，避免内存增长和任务间的会话状态泄漏。

Standard Answer:

Playwright shares a `Browser` but isolates a `BrowserContext` per job. Each context must be
closed in `finally` to avoid memory growth and session-state leaks between jobs.

Interview Review:

Strong answers connect cleanup to object ownership: shared Browser, isolated Context.

Production Case:

A worker that forgets to close contexts slowly leaks memory and leaves zombie browser
processes.

### Senior 4. Context managers in AI backends.

Question:

How do context managers apply to AI backends?

中文解析:

AI 请求会获取 LLM 流、Redis 连接、数据库会话和锁。即使生成失败也必须释放，所以要用上下文管理器包裹，防止 socket、连接和锁泄漏。

Standard Answer:

AI requests acquire LLM streams, Redis connections, database sessions, and locks. Each must
be released even when generation fails, so I wrap them in context managers to prevent socket,
connection, and lock leaks.

Interview Review:

This is a high-value AI Backend answer because it connects cleanup to streaming and
concurrency.

Production Case:

A leaked LLM stream keeps a socket open and can keep consuming tokens after the client
disconnects.

### Senior 5. Resource ownership in cleanup design.

Question:

Why should business logic not own resource management?

中文解析:

业务逻辑经常变化。如果清理依赖于每条代码路径都记得关闭资源，就很容易漏掉。上下文管理器拥有 Acquire 和 Release，业务逻辑只负责 Use。

English Standard Answer:

Business logic changes often. If cleanup depends on remembering to close resources on every
code path, leaks are inevitable. The context manager owns Acquire and Release, and the
business logic owns only the Use step.

Interview Review:

This is a separation-of-concerns answer and signals senior design judgment.

Production Case:

Mixing `conn.close()` into request handlers means any early return or exception path can leak
a connection.

---

# Day13 Async Programming

## Day13 Questions: Async Programming

### Beginner 1. What is async?

Question:

What is async?

中文解析:

异步是一种并发模型。单线程的事件循环在每个 await 处暂停一个 I/O 任务，去运行其他任务，等 I/O 就绪后再恢复。它提升的是 I/O 吞吐，不是 CPU 速度。

Standard Answer:

Async is a concurrency model where a single-threaded Event Loop runs many I/O-bound Tasks by
suspending each at `await` and resuming it when its I/O is ready. It improves I/O throughput,
not CPU speed.

Follow-up Question:

Does async make CPU-bound work faster?

Production Discussion:

Backend latency is mostly network and database I/O, which is exactly where async pays off.

### Beginner 2. What is await?

Question:

What is `await`?

中文解析:

await 暂停当前协程并释放事件循环，让其他任务运行，等待的 I/O 完成后再恢复。它不创建线程。

Standard Answer:

`await` suspends the current coroutine and releases the Event Loop so other Tasks can run,
then resumes when the awaited work is ready. It does not create a thread.

Follow-up Question:

Does `await` run code in parallel on multiple cores?

Production Discussion:

Because it is one thread, `await` overlaps waiting, not CPU computation.

### Beginner 3. What is a coroutine?

Question:

What is a coroutine?

中文解析:

协程是用 async def 定义的可暂停、可恢复的工作单元。调用它只创建一个协程对象（执行计划），并不执行函数体。

Standard Answer:

A coroutine is a pausable, resumable unit of work defined with `async def`. Calling it creates
a coroutine object, an execution plan the Event Loop runs.

Follow-up Question:

Why does calling `hello()` not print anything?

Production Discussion:

A coroutine that is never awaited or scheduled does nothing and raises a RuntimeWarning.

### Intermediate 1. Explain the Event Loop.

Question:

Explain the Event Loop.

中文解析:

事件循环是单线程的协作式调度器。它运行一个任务直到遇到 await，把它挂起，运行就绪队列里的其他任务，I/O 完成后再恢复它。

Standard Answer:

The Event Loop is a single-threaded cooperative scheduler. It runs a Task until an `await`,
suspends it, runs other ready Tasks, and resumes it when its I/O completes.

Follow-up Question:

How can one thread provide concurrency?

Production Discussion:

One worker serving many awaiting requests is why async backends scale for I/O-bound load.

### Intermediate 2. Task vs Coroutine.

Question:

What is the difference between a Task and a coroutine?

中文解析:

协程是执行计划；Task 是被事件循环驱动、创建后立即并发运行的协程。create_task 立刻调度，await coro() 是内联运行。

Standard Answer:

A coroutine is an execution plan. A Task is a coroutine scheduled on the Event Loop that runs
concurrently. `create_task` starts it now; `await coro()` runs it inline.

Follow-up Question:

When do you need a Task instead of a bare `await`?

Production Discussion:

Tasks enable concurrency because they start running before you await the result.

### Intermediate 3. What does gather() do?

Question:

What does `asyncio.gather()` do?

中文解析:

gather 并发运行多个协程，并按传入顺序返回结果，与完成顺序无关。

Standard Answer:

`gather()` runs multiple coroutines concurrently and returns their results in input order,
regardless of which finished first.

Follow-up Question:

Why is input order important when unpacking results?

Production Discussion:

Positional unpacking like `user, orders = await gather(...)` is only safe because order is
deterministic.

### Intermediate 4. Explain cancellation.

Question:

Explain Task cancellation.

中文解析:

取消是协作式的。task.cancel() 只是请求取消，CancelledError 在下一个 await 处抛出，需要在 except/finally 里清理并通常重新抛出。

Standard Answer:

Cancellation is cooperative. `task.cancel()` requests cancellation, and `CancelledError` is
raised at the next await, so cleanup runs before the Task ends.

Follow-up Question:

Why is cancellation not an immediate kill?

Production Discussion:

FastAPI cancels a request Task when the client disconnects; cleanup must release resources.

### Senior 1. How does async improve backend throughput?

Question:

How does async improve backend throughput?

中文解析:

后端延迟主要是 I/O。异步把等待重叠起来，一个 worker 能并发服务很多请求，而不是逐个阻塞。它提升 I/O 吞吐，不提升 CPU 速度。

Standard Answer:

Backend latency is mostly I/O, so async overlaps waiting and lets one worker serve many
concurrent requests instead of blocking on each. It raises I/O throughput, not CPU speed.

Interview Review:

Strong answers separate throughput from speed and mention the single thread.

Production Case:

A FastAPI worker awaiting OpenAI serves other requests during the wait instead of blocking.

### Senior 2. Explain Event Loop scheduling.

Question:

Explain Event Loop scheduling.

中文解析:

循环维护就绪队列和等待集合。运行一个任务到 await，移入等待，运行下一个就绪任务，I/O 完成后恢复等待者。整个过程单线程、协作式。

Standard Answer:

The loop keeps a ready queue and a waiting set. It runs a Task until `await`, moves it to
waiting, runs the next ready Task, and resumes waiters when their I/O completes. It is
cooperative and single-threaded.

Interview Review:

Good answers note that one blocking call freezes all scheduling.

Production Case:

A stray `time.sleep` in async code freezes every concurrent request on that worker.

### Senior 3. Why use a Semaphore?

Question:

Why use a Semaphore in async backends?

中文解析:

信号量限制并发数量，保护下游系统。无限 gather() 会触发限流、超时和连接池耗尽。目标是稳定吞吐，而不是最大并发。

Standard Answer:

A semaphore bounds concurrency to protect downstream systems. Unlimited `gather()` can trigger
rate limits, timeouts, and connection-pool exhaustion. The goal is stable throughput.

Interview Review:

Senior answers optimize for stable throughput, not maximum concurrency.

Production Case:

Limiting concurrent OpenAI calls to 10 avoids HTTP 429 and keeps latency predictable.

### Senior 4. How do you control production concurrency?

Question:

How do you control concurrency in production?

中文解析:

用带信号量的有界 gather()，尊重连接池大小，把阻塞工作放进 to_thread()，并 await 任务让异常暴露出来，目标是稳定吞吐。

Standard Answer:

Use bounded `gather()` with a semaphore, respect connection-pool sizes, keep blocking work in
`to_thread()`, and await Tasks so failures surface. Target stable throughput.

Interview Review:

Look for downstream capacity awareness: OpenAI, Redis, PostgreSQL, GPU, browser.

Production Case:

Embedding 100k texts is chunked behind a semaphore to respect rate limits and pool sizes.

### Senior 5. Explain FastAPI async architecture.

Question:

Explain FastAPI async architecture.

中文解析:

ASGI 服务器运行事件循环，每个请求是一个 Task。在 await 数据库或 API 时请求挂起，worker 服务其他请求；客户端断开会取消请求 Task。

Standard Answer:

An ASGI server runs an Event Loop; each request is a Task. At each `await` on the DB or an API,
the request suspends and the worker serves others. Client disconnects can cancel the request
Task.

Interview Review:

Strong answers mention `to_thread()` for blocking work and cancellation on disconnect.

Production Case:

An async endpoint awaiting PostgreSQL scales because the worker is not blocked during queries.

### Senior 6. How do you handle AI Backend concurrency?

Question:

How do you handle AI backend concurrency?

中文解析:

用 gather() 并发独立 I/O，用信号量限制外部调用，对 429 做退避重试，并 await 任务让异常可见，目标是稳定吞吐。

Standard Answer:

Run independent I/O with `gather()`, bound external calls with a semaphore, handle HTTP 429
with backoff, and await Tasks so exceptions are visible. Optimize for stable throughput.

Interview Review:

This connects async to real agent and RAG pipelines.

Production Case:

A RAG request concurrently fetches context from Redis and PostgreSQL, then calls the LLM under
a semaphore.

---

# Day14 Mini Project & Backend Architecture

## Day14 Questions: Backend Architecture

### Beginner 1. What is layered architecture?

Question:

What is layered architecture?

中文解析:

分层架构把系统拆成职责单一的层：API、Service、基础设施（Browser、LLM）、持久化（Repository、Database）。每一层可以独立变化。

Standard Answer:

Layered architecture splits a system into layers with single responsibilities — API, Service,
infrastructure, and persistence — so each can change independently.

Follow-up Question:

What should the API layer NOT do?

Production Discussion:

Mixing all layers into one route function makes the system untestable and fragile.

### Beginner 2. What is dependency injection?

Question:

What is dependency injection?

中文解析:

依赖注入是把组件的依赖从外部传入，而不是在内部创建，从而提升可测试性和解耦。

Standard Answer:

Dependency injection passes a component's dependencies from the outside instead of creating
them inside, improving testability and decoupling.

Follow-up Question:

How does FastAPI provide dependency injection?

Production Discussion:

`Depends()` gives request-scoped injection so tests can pass fakes.

### Beginner 3. What is a stateless service?

Question:

What is a stateless service?

中文解析:

无状态服务不在实例上保存每个请求的可变状态，因此在并发下安全，任意副本都能处理任意请求。

Standard Answer:

A stateless service keeps no per-request mutable state on the instance, so it is safe under
concurrency and any replica can handle any request.

Follow-up Question:

What goes wrong with shared mutable state?

Production Discussion:

Shared mutable state causes data leaks between users and race conditions.

### Intermediate 1. Why keep FastAPI routers thin?

Question:

Why should FastAPI routers stay thin?

中文解析:

路由只负责校验和委派，业务逻辑放进可复用、可测试的 Service。臃肿的路由重复逻辑且难以测试。

Standard Answer:

Routers should validate and delegate, keeping business logic in a reusable, testable service.
Fat routers duplicate logic and are hard to test.

Follow-up Question:

What belongs in `main.py`?

Production Discussion:

`main.py` only wires the app, routers, and dependencies.

### Intermediate 2. Why use the Repository pattern?

Question:

Why use the Repository pattern?

中文解析:

Repository 把数据库隐藏在方法后面，Service 不直接写 SQL，从而解耦并可在无真实数据库时测试。

Standard Answer:

The Repository pattern hides the database behind methods so the service is not coupled to SQL
and can be tested without a real database.

Follow-up Question:

What should the repository return?

Production Discussion:

It should return domain objects, not raw rows, so persistence details stop at the repository.

### Intermediate 3. Why hide the LLM behind an interface?

Question:

Why define an LLM interface instead of calling a provider directly?

中文解析:

接口让我们支持多provider、故障切换，并在测试中用假实现，而不改动业务流程。

Standard Answer:

An interface lets us support multiple providers, fail over, and mock the LLM in tests without
changing the workflow.

Follow-up Question:

How does multi-provider architecture improve reliability?

Production Discussion:

When one provider is down or rate-limited, the system fails over to another.

### Senior 1. How do you scale an AI summarization service?

Question:

How do you scale an AI summarization service?

中文解析:

用异步提升单 worker 的 I/O 吞吐，用队列和 worker pool 提升容量，对每个下游用信号量，429 时指数退避重试，并水平扩展副本。

Standard Answer:

Async for per-worker I/O throughput, a queue and worker pool for capacity, semaphores per
downstream dependency, and retries with exponential backoff. I scale replicas horizontally
behind the queue.

Interview Review:

Strong answers separate concurrency (async) from parallelism (workers) and name the
bottleneck.

Production Case:

Summarizing 10,000 URLs is bounded by OpenAI rate limits, so I cap concurrency and back off on
429.

### Senior 2. How do you keep a slow endpoint responsive?

Question:

The endpoint takes 30 seconds because the LLM is slow. How do you keep the API responsive?

中文解析:

在产品层面异步化：接收任务、立即返回 task_id、在 worker 中处理、暴露任务状态，让客户端轮询或被通知。

Standard Answer:

Accept the job, return a `task_id`, process it in a worker, and expose task status. The API
stays fast while the work runs in the background.

Interview Review:

Look for queue + worker + status, not holding the connection open.

Production Case:

A 30-second LLM job runs in a worker; the client polls `GET /tasks/{id}`.

### Senior 3. What is the most important trade-off here?

Question:

Would you maximize concurrency to make it faster?

中文解析:

不会。把并发限制在下游瓶颈内。无限并发会导致 429、超时和连接池耗尽，整体更慢。目标是稳定吞吐。

Standard Answer:

No. I bound concurrency to the downstream bottleneck. Unlimited concurrency causes 429s,
timeouts, and pool exhaustion, which is slower overall. I optimize for stable throughput.

Interview Review:

Senior engineers argue trade-offs, not absolutes.

Production Case:

Capping concurrent OpenAI calls keeps latency predictable under load.

### Senior 4. How do you decide layer boundaries?

Question:

How do you decide what belongs in each layer?

中文解析:

按单一职责划分：API 管传输，Service 管流程，基础设施层管外部系统，Repository 管持久化。依赖指向接口，而非细节。

Standard Answer:

By single responsibility: API owns transport, Service owns workflow, infrastructure layers own
external systems, and the Repository owns persistence. Dependencies point to interfaces, not
details.

Interview Review:

Good answers state what each layer must NOT do.

Production Case:

A browser layer returning FastAPI models is a boundary violation and creates tight coupling.

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

### Explain captured environment.

A captured environment is the outer-scope state that a closure preserves. The outer function
does not keep running, but the returned function object keeps access to the variables it
needs.

### Explain factory functions.

A factory function creates configured behavior. In Python, it often returns a closure that
captures configuration, such as a required role, timeout value, prompt style, or validation
rule.

### Explain closure vs class.

I use closures for small captured configuration and one main behavior. I use classes when
the state is complex, when there are multiple methods, or when lifecycle and observability
need to be explicit.

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
- Defining closure only as "a function inside another function."
- Forgetting that a closure captures variables, not fixed values.
- Capturing shared mutable state without clear ownership.
- Using closure state where a class would make lifecycle clearer.
- Capturing AI `messages` or Playwright `Page` objects in long-lived closures.
- Closing a resource after the work instead of in `finally`.
- Forgetting `try / finally` around `yield` in a `@contextmanager`.
- Returning `True` from `__exit__` and silently swallowing errors.
- Letting business logic own resource cleanup.
- Sharing a database session or Playwright context across jobs.
- Forgetting to close an LLM stream, leaking sockets and tokens.
- Calling `time.sleep()` or a blocking library inside `async def`.
- Calling a coroutine function without awaiting or scheduling it.
- Running unlimited `gather()` against rate-limited external services.
- Firing tasks and forgetting to await them, losing their exceptions.
- Expecting `task.cancel()` to stop a Task immediately.
- Using async for CPU-bound work instead of processes or threads.
- Putting business logic, scraping, and SQL in one route function.
- Constructing services inside routes instead of injecting them.
- Letting the service know about HTTP status codes or SQL.
- Sharing mutable state on a service instance across requests.
- Holding an HTTP connection open for a long LLM job.
- Maximizing concurrency instead of bounding it to the bottleneck.

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
- Captured environment means preserved outer-scope variables.
- `nonlocal` rebinds a name in the nearest enclosing function scope.
- Factory functions create configured behavior.
- Closure is good for small captured configuration.
- Class is better for complex state and lifecycle.
- Late binding means variables are looked up when the closure is called.
- `def f(i=i)` captures the current loop value as a default argument.
- Prefer explicit dependencies over global state.
- Use type hints for public functions.
- Production Python requires tests, logging, and clear structure.
- A context manager guarantees deterministic cleanup.
- Resource lifecycle is Acquire, Use, Release.
- `with` is `try / finally` with cleaner syntax.
- `__enter__` acquires; `__exit__` releases and sees exceptions.
- `__exit__` returning `True` suppresses the exception.
- `@contextmanager` uses `yield` for the resume-and-cleanup phase.
- `yield` must sit inside `try / finally`.
- Business logic should not own resource management.
- FastAPI `yield` dependencies close sessions in `finally`.
- Playwright isolates and closes a BrowserContext per job.
- AI backends wrap LLM streams, connections, and locks to prevent leaks.
- Async improves I/O throughput, not CPU speed.
- The Event Loop is single-threaded and cooperative.
- A blocking call inside `async def` freezes the whole loop.
- Calling a coroutine function creates a plan; it does not run.
- A coroutine is a plan; a Task is a coroutine the loop drives.
- `await` suspends the coroutine and releases the loop, no threads.
- `gather()` runs concurrently and returns input order.
- Cancellation is cooperative; `CancelledError` fires at the next await.
- A Task stores its exception until awaited.
- A `Semaphore` bounds concurrency for stable throughput.
- Use `asyncio.to_thread()` for unavoidable blocking work.
- Layered architecture separates transport, workflow, infrastructure, and persistence.
- Keep routers thin; services orchestrate; repositories hide the database.
- Browser and LLM layers return data, not FastAPI models.
- Dependency injection makes services testable, swappable, and stateless.
- Async gives per-worker throughput; workers and replicas give capacity.
- Semaphore, retry, and backoff protect downstream systems.
- Long jobs use a queue, worker, and task status.
- Optimize for stable throughput and name your trade-offs.
