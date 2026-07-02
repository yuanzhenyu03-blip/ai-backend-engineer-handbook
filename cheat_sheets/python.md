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
- "In production code, I prefer explicit dependencies and clear ownership of state."
