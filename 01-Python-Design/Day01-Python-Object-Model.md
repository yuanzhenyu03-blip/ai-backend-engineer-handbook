# Day 1 - Python Object Model

## Learning Objectives
- Understand that everything in Python is an object.
- Understand function objects, callable objects and references.
- Distinguish `==` from `is`.
- Understand mutable objects and the mutable default argument pitfall.

## Theory
Python variables do not store objects. They store references to objects.

> Variables are labels, not boxes.

Functions are first-class objects. They can be assigned to variables, passed as arguments and returned from other functions.

## Memory Model
```
hello ───────▶ Function Object
      \
       └────▶ a
```
Rebinding `hello = 5` changes only the reference held by `hello`; it does not modify the original function object referenced by `a`.

## Callable
`hello` is a function object.
`hello()` executes the callable object.
Objects implementing `__call__()` are also callable.

## == vs is
- `==` compares values.
- `is` compares object identity.

## Mutable Default Argument
Always prefer `None` over mutable defaults.

## Enterprise Practice
FastAPI commonly uses `None` as the default value for mutable parameters because mutable defaults can introduce shared state bugs.

## Tech Lead Review
❌ Reject:
```python
def create_user(tags=[]):
    ...
```

✅ Prefer:
```python
def create_user(tags=None):
    if tags is None:
        tags = []
```

## Interview Questions
1. Why are functions first-class objects?
2. Why does `hello` differ from `hello()`?
3. Explain `==` vs `is`.
4. Why is `tags=[]` dangerous?
5. Why does FastAPI prefer `None`?

## Today's Takeaway
Don't chase syntax. Understand Python's object model first.