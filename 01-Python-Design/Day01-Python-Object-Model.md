# Day 1 - Python Object Model

## Learning Objectives
- Understand that everything in Python is an object.
- Understand function objects and references.
- Distinguish `==` from `is`.
- Understand mutable objects and the mutable default argument pitfall.

## Key Ideas

### 1. Everything is an Object
Functions are objects and can be assigned to variables, passed as arguments, and returned from other functions.

### 2. Variables Hold References
Python variables are labels that reference objects rather than containing objects.

> Variables are labels, not boxes.

### 3. `==` vs `is`
- `==` compares values.
- `is` compares whether two variables reference the same object.

### 4. Mutable Default Argument
Avoid:

```python
def add(item, items=[]):
    items.append(item)
    return items
```

Prefer:

```python
def add(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

## Enterprise Practice
FastAPI commonly uses `None` as the default value for mutable parameters for this reason.

## Interview Questions
1. Why are functions first-class objects in Python?
2. Explain the difference between `==` and `is`.
3. Why is `tags=[]` considered a bad practice in production code?
4. Why does FastAPI frequently use `None` as a default argument?

## Today's Takeaway
Don't chase syntax. Understand the object model first.