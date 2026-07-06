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
