# Python Cheat Sheet

## Purpose

One-page Python interview review sheet for AI Backend Engineer preparation.

---

## Core Mental Model

```text
Name -> Reference -> Object
```

Every object has:

- identity
- type
- value

---

## `==` vs `is`

```python
a == b  # value equality
a is b  # object identity
```

Use:

```python
if value is None:
    ...

if status == "active":
    ...
```

Never use `is` for string or number value comparison.

---

## Mutable Default Argument

Bad:

```python
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items
```

Good:

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

Reason:

Default arguments are evaluated once at function definition time.

---

## Mutable vs Immutable

Mutable objects can change after creation.

Examples:

- `list`
- `dict`
- `set`

Immutable objects cannot change after creation.

Examples:

- `int`
- `float`
- `str`
- `bool`
- `tuple`, if all nested values are hashable

Core rule:

```text
Assignment changes what a name points to.
Mutation changes the object itself.
```

---

## Reference Assignment

```python
a = [1, 2]
b = a
b.append(3)

print(a)      # [1, 2, 3]
print(a is b) # True
```

`b = a` does not copy the list.

It binds `b` to the same list object.

Use `id()` to verify identity during learning:

```python
print(id(a) == id(b))  # True
```

---

## `append()` vs `+=` vs `a = a + [...]`

| Operation | Behavior | `id(a)` changes? | Other references see change? |
|-----------|----------|------------------|-------------------------------|
| `a.append(3)` | Mutates list in place | No | Yes |
| `a += [3]` | Mutates list in place | No | Yes |
| `a = a + [3]` | Creates new list and rebinds `a` | Yes | No |

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

---

## Shallow Copy vs Deep Copy

| Copy type | What is copied? | Nested objects shared? | Use when |
|-----------|------------------|-------------------------|----------|
| `copy.copy()` | First layer | Yes | Outer container isolation is enough |
| `copy.deepcopy()` | Full object tree | No | Full isolation is required |

Shallow copy example:

```python
import copy

original = [["python"]]
cloned = copy.copy(original)
cloned[0].append("fastapi")

print(original)  # [['python', 'fastapi']]
```

Deep copy example:

```python
import copy

original = [["python"]]
cloned = copy.deepcopy(original)
cloned[0].append("fastapi")

print(original)  # [['python']]
```

---

## Hashable vs Unhashable

Hashable objects can be dictionary keys.

Unhashable objects cannot.

| Object | Hashable? | Reason |
|--------|-----------|--------|
| `str` | Yes | Immutable |
| `int` | Yes | Immutable |
| `tuple` | Sometimes | Only if all nested values are hashable |
| `list` | No | Mutable |
| `dict` | No | Mutable |
| `set` | No | Mutable |

Valid:

```python
cache = {("user", 1): "active"}
```

Invalid:

```python
cache = {["user", 1]: "active"}
```

Also invalid:

```python
cache = {("user", [1, 2]): "active"}
```

Reason:

The tuple contains a list, and the list is unhashable.

---

## Function Parameter Passing

Python passes object references by value.

This model is also called call by sharing.

Core rule:

```text
Function parameters are local names.
They point to the same objects passed by the caller.
```

Example:

```python
def add_item(items: list[int]) -> None:
    items.append(3)


values = [1, 2]
add_item(values)

print(values)  # [1, 2, 3]
```

Why:

`items` and `values` point to the same list object.

---

## Mutation vs Rebinding

Mutation changes the object.

Rebinding changes what a local name points to.

| Operation | Caller sees change? | Reason |
|-----------|---------------------|--------|
| `items.append(3)` | Yes | Mutates shared list |
| `items += [3]` | Yes | Mutates shared list |
| `items = items + [3]` | No | Rebinds local name |
| `items = [1, 2, 3]` | No | Rebinds local name |

Example:

```python
def add_with_plus(items: list[int]) -> None:
    items = items + [3]


values = [1, 2]
add_with_plus(values)

print(values)  # [1, 2]
```

If a function creates a new object, return it:

```python
def add_with_return(items: list[int]) -> list[int]:
    return items + [3]
```

---

## Mutable vs Immutable in Function Calls

Mutable arguments can be changed in place:

```python
def add_role(user: dict[str, str]) -> None:
    user["role"] = "admin"
```

Immutable arguments cannot be changed in place:

```python
def increment(value: int) -> None:
    value = value + 1
```

The `increment()` function only rebinds the local name `value`.

---

## Common Mutable Methods

These methods usually mutate in place:

| Type | Methods |
|------|---------|
| `list` | `append`, `extend`, `insert`, `remove`, `pop`, `sort`, `reverse`, `clear` |
| `dict` | `update`, `setdefault`, `pop`, `clear` |
| `set` | `add`, `update`, `remove`, `discard`, `clear` |

Interview warning:

```text
If a function calls one of these methods on a parameter,
it may change caller-visible state.
```

---

## Scope & LEGB

Python name lookup follows LEGB:

```text
Local -> Enclosing -> Global -> Built-in
```

Meaning:

- Local: current function scope
- Enclosing: outer function scopes
- Global: module scope
- Built-in: Python built-ins such as `len`, `print`, `dict`

Python uses lexical scope:

```text
A function searches names based on where it is defined,
not where it is called.
```

---

## `global`

`global` tells Python to bind a name in module global scope.

```python
count = 0


def add() -> None:
    global count
    count += 1
```

Use rarely.

Backend rule:

```text
Do not store request state in global variables.
```

---

## `nonlocal`

`nonlocal` tells Python to bind a name in the nearest enclosing function scope.

```python
def outer():
    count = 0

    def inner():
        nonlocal count
        count += 1
        return count

    return inner
```

Use when closure state must be rebound intentionally.

---

## Closure

Engineering definition:

```text
Closure = Function Object + Captured Environment
```

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

The returned function keeps access to `count` even after `make_counter()` returns.

---

## Late Binding

Closures look up captured variables when called, not when created.

Bug:

```python
def make_funcs():
    funcs = []

    for i in range(3):
        def f():
            return i

        funcs.append(f)

    return funcs
```

All functions return:

```text
2
2
2
```

Fix:

```python
def f(i=i):
    return i
```

Now each function keeps its own default value.

---

## Function Objects

```python
def normalize(value: str) -> str:
    return value.strip().lower()

handler = normalize
result = handler(" USER ")
```

Functions can be:

- assigned
- passed
- returned
- stored in dictionaries
- used by frameworks

---

## Callable Objects

```python
class Prefixer:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def __call__(self, value: str) -> str:
        return f"{self.prefix}{value}"
```

Use callable objects when behavior needs configuration.

---

## Enterprise Rules

- Avoid hidden shared mutable state.
- Make mutation obvious.
- Use type hints.
- Use logging instead of `print()` in production.
- Keep functions small and readable.
- Prefer dependency injection over globals.
- Write tests for important behavior.

---

## Interview Phrases

- "Variables in Python are names bound to object references."
- "`==` compares values, while `is` compares identity."
- "Functions are first-class objects in Python."
- "Mutable defaults can leak state across calls."
- "Assignment copies references, not necessarily objects."
- "A shallow copy copies the outer container, but nested objects may still be shared."
- "A deep copy recursively copies the object tree."
- "Dictionary keys must be hashable because their hash must remain stable."
- "Python uses call by sharing for function arguments."
- "Mutation changes the object; rebinding changes the local name."
- "Rebinding a parameter does not rebind the caller's variable."
- "Python uses lexical scope, not dynamic scope."
- "LEGB means Local, Enclosing, Global, Built-in."
- "A closure is a function object plus a captured environment."
- "Late binding means a closure looks up a variable when the function is called."
- "In production code, I prefer explicit dependencies and clear ownership of state."
