# CODING_STANDARD.md

# AI Backend Engineering Coding Standard

## Philosophy

Code is written for humans first, computers second.

Always prefer clarity over cleverness.

---

# Python Version

Python 3.12+

---

# Formatting

* Follow PEP 8
* Use Black formatter
* Use Ruff for linting
* Maximum line length: 88

---

# Type Hints

Required for all public functions.

Example:

```python
def create_user(name: str) -> dict:
    ...
```

---

# Naming

Variables:
snake_case

Functions:
snake_case

Classes:
PascalCase

Constants:
UPPER_CASE

Private members:
_prefix

---

# Mutable Defaults

Never write:

```python
def foo(items=[]):
    ...
```

Always write:

```python
def foo(items: list | None = None):
    if items is None:
        items = []
```

---

# Function Design

Functions should do one thing only.

Prefer pure functions whenever possible.

Avoid hidden side effects.

---

# Project Structure

Each project should contain:

```text
app/
tests/
docs/
requirements.txt
README.md
```

---

# Error Handling

Never silently ignore exceptions.

Catch only expected exceptions.

Always provide meaningful error messages.

---

# Logging

Use the logging module.

Never use print() in production code.

---

# API Design

* RESTful naming
* Consistent HTTP status codes
* Request validation
* Response models

---

# FastAPI Rules

* Dependency Injection
* Pydantic Models
* Async where appropriate
* Never use mutable default parameters

---

# Playwright Rules

* Prefer Locator API
* Avoid unnecessary sleep()
* Use explicit waiting
* Separate page objects

---

# Database Rules

* Parameterized queries
* Migrations with Alembic
* Clear transaction boundaries

---

# Git Rules

Commit messages:

```text
feat:
fix:
refactor:
docs:
test:
chore:
```

---

# Testing

Every important feature should have tests.

Target coverage:

80%+

---

# Code Review Checklist

Before merging, ask:

* Is the code readable?
* Is the naming clear?
* Are there hidden side effects?
* Are types complete?
* Is error handling sufficient?
* Would a teammate understand this in six months?

---

# Engineering Principle

Don't chase tools.

Build engineering capability.
