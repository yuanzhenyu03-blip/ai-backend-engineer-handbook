# GLOSSARY.md

# Technical Glossary

This file collects important English technical terms for interviews and engineering work.

---

## Python Terms

### Object

An object is a value with identity, type, and state.

Interview phrase:

> In Python, almost everything is an object.

---

### Reference

A reference is a variable's link to an object.

Interview phrase:

> Python variables store references to objects, not the objects themselves.

---

### Mutable

A mutable object can be changed after creation.

Examples:

- list
- dict
- set

---

### Immutable

An immutable object cannot be changed after creation.

Examples:

- int
- str
- tuple
- frozenset

---

### Callable

A callable object can be called with parentheses.

Example:

```python
func()
```

Interview phrase:

> A function object is callable because it implements call behavior.

---

### Identity

Object identity tells whether two variables point to the same object.

Python operator:

```python
a is b
```

---

### Equality

Equality checks whether two objects have the same value.

Python operator:

```python
a == b
```

---

### Mutable Default Argument

A common Python bug caused by using a mutable object as a default function parameter.

Bad:

```python
def add(item, items=[]):
    items.append(item)
    return items
```

Good:

```python
def add(item, items: list | None = None):
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## Backend Terms

### Dependency Injection

A design pattern where dependencies are provided to a function or class instead of being created inside it.

---

### API

Application Programming Interface.

A contract between software systems.

---

### REST

A common API design style based on resources and HTTP methods.

---

### Middleware

Code that runs between the request and the final response.

---

## AI Terms

### LLM

Large Language Model.

Examples:

- GPT
- Claude
- Gemini

---

### Tool Calling

A mechanism where an LLM calls external tools or functions.

---

### RAG

Retrieval-Augmented Generation.

A system where an LLM retrieves external knowledge before generating an answer.

---

### MCP

Model Context Protocol.

A protocol for connecting AI models with tools and external systems.
