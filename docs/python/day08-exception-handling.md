# Lesson 8 — Exception Handling

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day07 — Iterators & Generators

Next Lesson: Day09 — Modules & Packages

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain Python exception handling in engineering language.
* Use `try` and `except` correctly.
* Catch specific exceptions such as `ZeroDivisionError`.
* Explain why `except Exception` should not be the default habit.
* Explain exception control flow inside a `try` block.
* Explain exception propagation through the call stack.
* Use `raise` for invalid business rules.
* Design custom exceptions such as `InvalidPromptError`.
* Explain exception chaining with `raise ... from ...`.
* Read traceback from symptom to root cause.
* Connect exceptions to FastAPI `HTTPException`, Playwright automation failures,
  and AI backend error design.

---

# Why This Matters

Backend engineering is not only about the happy path.

The happy path says:

```text
request comes in -> code runs -> response returns
```

Production says:

```text
request comes in
        |
        +--> invalid input
        +--> database timeout
        +--> browser selector missing
        +--> LLM rate limit
        +--> tool execution failed
        +--> network reset
        +--> bug in our own code
```

Tech Lead Question:

If something goes wrong, should the backend silently return `None`?

Think first.

Common wrong answer:

Maybe return `False` or `None`, and the caller can check it.

Expected student answer:

For expected business outcomes, returning a value can be fine. But for invalid states,
failed dependencies, or broken assumptions, raising an exception is clearer because it
forces the error path to be handled.

Tech Lead explanation:

Exceptions are not just syntax.

They are a system design tool.

They answer:

```text
Can this function continue safely?
If not, who should handle the failure?
```

This is why Day08 matters for AI backend engineering.

FastAPI needs exceptions to turn backend failures into correct HTTP responses.

Playwright needs exceptions to recover from automation failures, capture screenshots, and
clean up browser contexts.

AI backends need exceptions to distinguish prompt validation errors, LLM API failures,
tool failures, rate limits, and internal bugs.

If errors are represented only as `None`, every caller must guess what happened.

If errors are represented as clear exceptions, the system can route failure to the right
layer.

---

# Roadmap Position

Day08 follows Day07 naturally.

In Day07, `StopIteration` showed that exceptions are not always crashes.

They can also be protocol signals.

Today we broaden that idea:

```text
Day07: StopIteration as protocol control flow
        |
        v
Day08: Exception handling as production control flow
        |
        v
FastAPI HTTP errors
        |
        v
Playwright recovery and cleanup
        |
        v
AI backend error boundaries
```

After this lesson, Day09 moves into modules and packages.

That matters because production exception design often requires a dedicated module:

```text
app/
  errors.py
  services/
  api/
```

Large systems do not scatter random exception classes everywhere.

They organize error design.

---

# Lesson Map

```text
Today's Lesson

1. Why Exceptions Matter
2. try / except
3. Specific Exceptions
4. Exception Control Flow
5. Exception Propagation
6. raise
7. Return None vs Raise
8. Custom Exceptions
9. Exception Chaining
10. Traceback and Root Cause
11. FastAPI HTTPException
12. Playwright Failure Handling
13. AI Backend Error Design
14. Interview Review
```

---

# Estimated Study Time

Reading: 90-120 minutes

Exercises: 90-120 minutes

Coding: 60-90 minutes

Review: 30-45 minutes

Total: 4-5 hours

---

# Main Concepts

## 1. Basic `try` / `except`

The basic syntax:

```python
try:
    risky_code()
except SomeError:
    handle_error()
```

Classroom example:

```python
def divide(a: int, b: int) -> float | None:
    try:
        return a / b
    except ZeroDivisionError:
        print("Cannot divide by zero")
        return None
```

Classroom record:

Student version:

```python
def divide(a: int, b: int):
    try:
        print(a / b)
    except Exception:
        print("error")
```

Tech Lead Review:

This version proves the student understands the basic `try / except` shape, but it hides
too much.

Problems:

* It catches `Exception` instead of the specific failure.
* It prints the result instead of returning it.
* It gives a vague error message.
* It makes the function harder to reuse in backend code.

Recommended classroom version:

```python
def divide(a: int, b: int) -> float | None:
    try:
        return a / b
    except ZeroDivisionError:
        print("Cannot divide by zero")
        return None
```

Why this is better:

* It catches the exact error we expect.
* It returns a value to the caller.
* It gives a clear classroom-visible message.
* It does not hide unrelated bugs.

Tech Lead Question:

What problem does `try / except` solve?

Think first.

Common wrong answer:

It prevents the program from crashing.

Expected student answer:

It lets us handle a known failure path at the correct layer.

Tech Lead explanation:

The goal is not to hide every crash.

The goal is to handle expected failures intentionally.

```text
expected failure -> handle clearly
unexpected bug   -> do not hide it
```

## 2. Catch Specific Exceptions

Bad habit:

```python
try:
    result = 10 / value
except Exception:
    result = 0
```

Why is this dangerous?

Because `Exception` catches many different errors.

It may hide:

* `ZeroDivisionError`
* `TypeError`
* `NameError`
* bugs from a helper function
* unexpected state corruption

Better:

```python
def safe_divide(a: int, b: int) -> float:
    try:
        return a / b
    except ZeroDivisionError:
        return 0.0
```

Tech Lead rule:

```text
Catch the exception you know how to handle.
Let the exception you do not understand propagate.
```

This is production discipline.

## 3. `ZeroDivisionError`

`ZeroDivisionError` happens when dividing by zero.

```python
print(10 / 0)
```

This raises:

```text
ZeroDivisionError
```

Precision matters:

```python
try:
    value = 10 / denominator
except ZeroDivisionError:
    value = 0
```

This says:

```text
I expect denominator may be zero.
I know how to handle that case.
```

It does not hide unrelated bugs.

## 4. Exception Control Flow

Important classroom point:

When an exception happens inside a `try` block, the remaining lines in that `try` block do
not continue.

Example:

```python
try:
    print("A")
    result = 10 / 0
    print("B")
except ZeroDivisionError:
    print("C")

print("D")
```

Output:

```text
A
C
D
```

Why not `B`?

Because execution jumps from the failing line to the matching `except` block.

ASCII flow:

```text
try:
  print("A")       -> runs
  10 / 0           -> raises ZeroDivisionError
  print("B")       -> skipped
        |
        v
except ZeroDivisionError:
  print("C")       -> runs
        |
        v
after try/except:
  print("D")       -> runs
```

Tech Lead Question:

Why does this matter in backend code?

Expected student answer:

Because any cleanup or state update after the failing line may not run unless it is handled
properly.

## 5. Exception Propagation

If a function does not catch an exception, the exception moves up the call stack.

Example:

```python
def parse_number(value: str) -> int:
    return int(value)


def load_user_age(raw_age: str) -> int:
    return parse_number(raw_age)


def handle_request(raw_age: str) -> int:
    return load_user_age(raw_age)


handle_request("abc")
```

`int("abc")` raises `ValueError`.

If `parse_number()` does not catch it, it propagates upward:

```text
parse_number()
        |
        v
load_user_age()
        |
        v
handle_request()
        |
        v
framework / caller
```

This is exception propagation.

Tech Lead explanation:

Not every function should catch every error.

Sometimes the correct design is:

```text
low-level function detects failure
        |
        v
exception propagates
        |
        v
framework boundary converts it to response/log/retry
```

## 6. `raise`

`raise` actively creates an exception.

Example:

```python
def check_age(age: int) -> str:
    if age < 18:
        raise ValueError("Age must be at least 18.")

    return "Access granted"
```

Tech Lead Question:

Why actively raise instead of returning `False`?

Think first.

Common wrong answer:

Returning `False` is simpler.

Expected student answer:

If invalid age means the function cannot continue safely, raising makes the failure
explicit and forces the caller or framework to handle it.

Engineering explanation:

Returning `False` can be ignored.

Returning `None` can be confused with valid absence.

Raising an exception says:

```text
The requested operation is invalid.
Stop normal execution.
Route this failure to an error handler.
```

Classroom warning:

Do not design code that raises and catches its own business exception in the same small
function just to continue.

Weak pattern:

```python
def check_age(age: int) -> str:
    try:
        if age < 18:
            raise ValueError("Age must be at least 18.")
    except ValueError:
        return "Access denied"

    return "Access granted"
```

Why this is not recommended:

The same function creates the failure and immediately hides it. A cleaner design raises at
the validation layer and lets the caller or API boundary decide how to respond.

## 7. Return `None` vs Raise

Returning `None` is fine when absence is expected.

Example:

```python
def find_user(user_id: int) -> dict[str, str] | None:
    return None
```

This can mean:

```text
No user was found.
```

Raising is better when an invariant is broken.

```python
def validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
```

Classroom distinction:

```text
Expected absence -> return None
Invalid operation -> raise
External failure -> raise or translate at boundary
```

## 8. Custom Exception

Custom exceptions make error meaning explicit.

Example:

```python
class InvalidPromptError(ValueError):
    """Raised when a prompt violates application rules."""
```

Usage:

```python
def validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        raise InvalidPromptError("prompt must not be empty")

    if len(prompt) > 4000:
        raise InvalidPromptError("prompt is too long")
```

Why custom exceptions?

Because production systems need to distinguish:

* invalid prompt
* model timeout
* rate limit
* tool execution failure
* database failure
* internal bug

If everything is just `Exception`, the system loses meaning.

## 9. Exception Chaining: `raise ... from ...`

Sometimes low-level errors should be translated into domain errors.

Example:

```python
class LLMRequestError(RuntimeError):
    """Raised when an LLM request fails."""


def call_llm(prompt: str) -> str:
    try:
        return external_llm_call(prompt)
    except TimeoutError as error:
        raise LLMRequestError("LLM request timed out") from error
```

`raise ... from ...` keeps the original cause.

Without chaining:

```text
LLMRequestError happened
```

With chaining:

```text
TimeoutError happened
        |
        v
LLMRequestError was raised from that root cause
```

This matters for production debugging.

The user-facing message may be simple.

The traceback should still preserve root cause.

## 10. Traceback and Root Cause

A traceback is the path Python shows when an exception is not handled.

It tells you:

* where the exception was raised
* which functions were called
* what line failed
* what exception type occurred
* what message was attached

Root cause thinking:

```text
Symptom:
API returned 500

Traceback:
Route -> service -> LLM client -> TimeoutError

Root Cause:
External model provider timed out
```

Tech Lead Question:

Should production logs only say "request failed"?

Expected answer:

No. Logs should preserve enough structured context to identify the failing layer and root
cause, without leaking sensitive data.

## 11. FastAPI `HTTPException`

FastAPI uses `HTTPException` to convert backend failure into HTTP responses.

Example:

```python
from fastapi import HTTPException


def get_user(user_id: int) -> dict[str, int]:
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="invalid user id")

    return {"user_id": user_id}
```

This is useful at API boundaries.

But do not put `HTTPException` everywhere in domain code.

Better design:

```text
domain/service layer -> raises domain exception
API layer            -> converts to HTTPException
```

That keeps business logic independent from HTTP.

## 12. Playwright Automation Failures

Playwright automation fails in expected ways:

* locator timeout
* page crash
* navigation timeout
* login expired
* selector changed
* browser context closed

Example pattern:

```python
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


async def click_with_screenshot(page, locator) -> None:
    try:
        await locator.click(timeout=5000)
    except PlaywrightTimeoutError:
        await page.screenshot(path="click-timeout.png")
        raise
```

The key is not to hide the failure.

The key is:

```text
capture evidence
clean up resources
re-raise or translate clearly
```

## 13. AI Backend Error Design

AI backends need clear error categories.

Examples:

```python
class InvalidPromptError(ValueError):
    pass


class LLMRequestError(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


class RateLimitError(RuntimeError):
    pass
```

Why?

Because different errors need different responses:

| Error | Likely Handling |
|-------|-----------------|
| `InvalidPromptError` | Return 400 to user |
| `RateLimitError` | Retry later or return 429 |
| `LLMRequestError` | Log, retry, fallback model, or return 503 |
| `ToolExecutionError` | Mark tool call failed, preserve trace |
| internal bug | Alert team, return generic 500 |

Production principle:

```text
Error type is part of system design.
```

---

# Engineering Thinking

Exception handling is not about catching everything.

It is about drawing boundaries.

```text
Where is the error detected?
Where is it translated?
Where is it logged?
Where is it shown to the user?
```

## Catch Where You Can Add Meaning

Do not catch an exception just because you can.

Catch it when you can:

* recover
* add context
* translate it
* clean up resources
* convert it to a correct API response

If you cannot do any of those, let it propagate.

## Specific Exceptions Preserve Meaning

`except Exception` is sometimes needed at a process boundary.

Examples:

* background worker top-level handler
* request boundary logging
* task scheduler safety wrapper

But inside normal business logic, broad catching often hides bugs.

Tech Lead review:

```text
If you catch Exception, explain why this is the correct boundary.
```

## Return Values vs Exceptions

Return values are good for expected outcomes.

Exceptions are good for broken assumptions or failed operations.

```text
user not found       -> maybe return None
invalid prompt       -> raise InvalidPromptError
LLM request timeout  -> raise LLMRequestError
browser timeout      -> capture evidence and raise
```

## Traceback Is A Debugging Story

A traceback is not noise.

It is a story:

```text
Who called whom?
Where did it fail?
What was the root cause?
Was the error translated clearly?
```

Good production systems preserve this story.

Bad systems replace it with:

```text
Something went wrong.
```

---

# Classroom Exercises

## Exercise 1: `try / except` Output Prediction

Starter Code:

```python
try:
    print("A")
    print(10 / 0)
    print("B")
except ZeroDivisionError:
    print("C")

print("D")
```

Expected Output:

```text
A
C
D
```

Explanation:

After `10 / 0` raises `ZeroDivisionError`, the rest of the `try` block is skipped.

Follow-up Question:

Why does `"B"` not print?

## Exercise 2: Precise `ZeroDivisionError`

Starter Code:

```python
def divide(a: int, b: int) -> float | None:
    try:
        return a / b
    except ZeroDivisionError:
        print("Cannot divide by zero")
        return None
```

Expected Output:

```text
divide(10, 0) prints "Cannot divide by zero" and returns None
```

Explanation:

The function handles the specific failure it understands.

Follow-up Question:

Why is `except Exception` worse here?

## Exercise 3: Exception Propagation

Starter Code:

```python
def parse_age(value: str) -> int:
    return int(value)


def load_age(raw: str) -> int:
    return parse_age(raw)


def handle(raw: str) -> int:
    return load_age(raw)


handle("abc")
```

Expected Output:

```text
ValueError propagates from parse_age -> load_age -> handle
```

Explanation:

No function catches the exception, so it moves up the call stack.

Follow-up Question:

Which layer should translate this into an API response?

## Exercise 4: `raise`

Starter Code:

```python
def check_age(age: int) -> str:
    if age < 18:
        raise ValueError("Age must be at least 18.")

    return "Access granted"
```

Expected Output:

```text
check_age(17) raises ValueError
check_age(18) returns "Access granted"
```

Explanation:

Being under 18 violates the classroom business rule. The function cannot continue safely,
so it raises instead of returning a vague failure value.

Follow-up Question:

Why not return `False`?

## Exercise 5: Custom Exception

Starter Code:

```python
class InvalidPromptError(ValueError):
    pass


def validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        raise InvalidPromptError("prompt must not be empty")
```

Expected Output:

```text
validate_prompt("") raises InvalidPromptError
```

Explanation:

The error type carries domain meaning.

Follow-up Question:

How should FastAPI convert this error?

## Exercise 6: Exception Chaining

Starter Code:

```python
class LLMRequestError(RuntimeError):
    pass


def call_llm() -> str:
    try:
        raise TimeoutError("provider timed out")
    except TimeoutError as error:
        raise LLMRequestError("LLM request failed") from error
```

Expected Output:

```text
LLMRequestError caused by TimeoutError
```

Explanation:

`raise ... from ...` preserves the original root cause.

Follow-up Question:

Why is this better than raising a new error without `from`?

## Exercise 7: FastAPI `HTTPException`

Starter Code:

```python
from fastapi import HTTPException


def read_user(user_id: int) -> dict[str, int]:
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="invalid user id")

    return {"user_id": user_id}
```

Expected Output:

```text
Invalid user id becomes HTTP 400.
```

Explanation:

`HTTPException` is useful at the API boundary.

Follow-up Question:

Should every service function raise `HTTPException` directly?

## Exercise 8: Playwright Timeout Evidence

Starter Code:

```python
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


async def click_login(page, locator) -> None:
    try:
        await locator.click(timeout=5000)
    except PlaywrightTimeoutError:
        await page.screenshot(path="login-timeout.png")
        raise
```

Expected Output:

```text
On timeout, capture screenshot and re-raise.
```

Explanation:

The worker keeps evidence and does not silently hide the automation failure.

Follow-up Question:

What cleanup should happen after browser automation fails?

## Exercise 9: AI Backend Error State

Starter Code:

```python
class ToolExecutionError(RuntimeError):
    pass


def run_tool(name: str) -> str:
    if name == "dangerous":
        raise ToolExecutionError("tool failed")

    return "ok"
```

Expected Output:

```text
run_tool("dangerous") raises ToolExecutionError
```

Explanation:

Tool failures should be explicit so the agent can record failed tool state.

Follow-up Question:

Should a tool failure always crash the whole AI conversation?

---

# FastAPI Connections

FastAPI is an exception boundary.

At the API layer, exceptions become HTTP responses.

Example:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.get("/users/{user_id}")
def read_user(user_id: int) -> dict[str, int]:
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="invalid user id")

    return {"user_id": user_id}
```

Why this matters:

```text
Python exception
        |
        v
FastAPI exception handler
        |
        v
HTTP response
```

Production design:

* Validate request input.
* Raise domain exceptions in service code.
* Translate domain exceptions at API boundaries.
* Do not leak internal tracebacks to users.
* Log enough context for root cause analysis.

AI Backend example:

```python
class InvalidPromptError(ValueError):
    pass


def validate_prompt(prompt: str) -> None:
    if not prompt.strip():
        raise InvalidPromptError("prompt must not be empty")
```

API boundary:

```python
try:
    validate_prompt(prompt)
except InvalidPromptError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
```

---

# Playwright Connections

Playwright jobs interact with unstable external state.

Expected failures:

* timeout
* missing locator
* navigation failure
* expired session
* page crash
* changed UI

A production worker should separate recoverable and non-recoverable errors.

Recoverable:

```text
temporary timeout -> retry with limit
```

Non-recoverable:

```text
login invalid -> stop job and mark failed
```

Example:

```python
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


async def run_job(page) -> None:
    try:
        await page.get_by_role("button", name="Export").click(timeout=5000)
    except PlaywrightTimeoutError:
        await page.screenshot(path="export-timeout.png")
        raise
    finally:
        await page.context.close()
```

Engineering thinking:

* Capture evidence before cleanup.
* Do not swallow automation errors.
* Close browser contexts.
* Preserve root cause.
* Make retry decisions explicit.

AI Backend connection:

If an AI agent uses Playwright as a tool, automation errors should become structured tool
failures, not random `None` results.

---

# English Interview

## Key Vocabulary

* exception handling
* `try`
* `except`
* specific exception
* `ZeroDivisionError`
* exception propagation
* call stack
* `raise`
* custom exception
* exception chaining
* traceback
* root cause
* `HTTPException`

## Beginner Questions

### What is exception handling in Python?

Standard Answer:

Exception handling is the mechanism Python uses to respond to errors or exceptional
conditions with `try`, `except`, and `raise`.

Engineering Perspective:

In backend systems, exception handling defines where failures are detected, logged,
translated, and shown to users.

### What is the difference between `try/except` and normal control flow?

Standard Answer:

Normal control flow handles expected branches. `try/except` handles failures that interrupt
normal execution.

Engineering Perspective:

Use normal return values for expected outcomes and exceptions for invalid operations or
failed dependencies.

### Why should we catch specific exceptions instead of using `except Exception`?

Standard Answer:

Specific exceptions preserve meaning and avoid hiding unexpected bugs.

Engineering Perspective:

In production code, catching `Exception` too early can hide root causes and make debugging
much harder.

## Intermediate Questions

### What is exception propagation?

Standard Answer:

Exception propagation means an exception moves up the call stack until a caller handles it
or the program/framework reports it.

Engineering Perspective:

Propagation lets lower-level code detect failure while higher-level boundaries decide how
to log, retry, or convert it to a response.

### What happens when an exception is raised inside a nested function call?

Standard Answer:

If the nested function does not handle it, the exception propagates to the caller, then to
the caller's caller, and so on.

Engineering Perspective:

This helps backend services centralize error handling at request, worker, or task
boundaries.

### What is the difference between returning `None` and raising an exception?

Standard Answer:

Returning `None` can represent expected absence. Raising an exception represents an invalid
operation, failed dependency, or broken assumption.

Engineering Perspective:

Use `None` only when the caller can reasonably continue. Raise when normal execution should
stop.

### Why should validation logic raise `ValueError` or custom exceptions?

Standard Answer:

Validation failures mean input violates required rules. Raising `ValueError` or a custom
exception makes that failure explicit.

Engineering Perspective:

Custom validation exceptions help API layers return correct 400 responses and help AI
systems classify prompt failures.

## Senior Questions

### How would you design exception handling in a production FastAPI service?

Standard Answer:

I would use domain-specific exceptions in service code, translate them to `HTTPException`
or registered exception handlers at the API boundary, log root causes internally, and avoid
leaking internal tracebacks to users.

Engineering Perspective:

This separates business logic from HTTP while still giving clients correct status codes.

### How does exception propagation support framework-level error handling?

Standard Answer:

Propagation allows exceptions from lower layers to reach framework boundaries where they
can be converted into standardized responses or task failure records.

Engineering Perspective:

Framework-level handling avoids duplicating error conversion logic in every function.

### Why are custom exceptions useful in large backend systems?

Standard Answer:

Custom exceptions encode domain meaning and let the system handle different failure types
differently.

Engineering Perspective:

An `InvalidPromptError`, `LLMRequestError`, and `ToolExecutionError` should not all be
handled the same way.

### What problem does `raise ... from ...` solve?

Standard Answer:

It preserves the original cause when translating a low-level exception into a higher-level
domain exception.

Engineering Perspective:

It keeps traceback useful for root cause analysis while still giving the application a
domain-specific error type.

### How would you handle LLM API failures in an AI Backend system?

Standard Answer:

I would classify failures such as rate limits, timeouts, provider errors, and invalid
requests. I would use retries for safe transient failures, fallback behavior where
appropriate, structured logs, and domain exceptions such as `LLMRequestError`.

Engineering Perspective:

Do not collapse all LLM failures into `None` or generic 500. The error type should guide
retry, user message, alerting, and state updates.

### How should Playwright automation workers handle recoverable vs non-recoverable errors?

Standard Answer:

Recoverable errors such as temporary timeouts can be retried with limits. Non-recoverable
errors such as invalid login or missing required state should fail the job clearly.

Engineering Perspective:

Workers should capture evidence, clean up browser contexts, preserve root cause, and avoid
infinite retries.

---

# Today's Takeaway

Exception handling is production control flow.

The syntax is small:

```python
try:
    ...
except SpecificError:
    ...
```

The engineering idea is larger:

```text
Detect failure where it happens.
Handle failure where meaning can be added.
Let unexpected bugs surface.
Preserve root cause.
```

Use precise exceptions.

Use `raise` for invalid operations.

Use custom exceptions for domain meaning.

Use `raise ... from ...` to preserve root cause.

FastAPI turns exceptions into HTTP responses.

Playwright workers use exceptions for evidence, retry, and cleanup.

AI backends use exceptions to classify prompt, model, tool, and rate-limit failures.

---

## Today's Tech Lead Advice

Exceptions are not just for reporting errors.

They are a mechanism for controlling failure in production systems.

Good exception design helps the team decide:

* which layer owns the failure
* which failures can be retried
* which failures should stop immediately
* which details are safe to show users
* which root cause must be preserved for debugging

The point is not to make code louder.

The point is to make failure understandable.

---

# Before Next Lesson Checklist

Before Day09, confirm you can answer these without notes:

- [ ] What does `try / except` do?
- [ ] Why should you catch `ZeroDivisionError` specifically?
- [ ] Why is `except Exception` risky?
- [ ] What happens to later lines in a `try` block after an exception?
- [ ] What is exception propagation?
- [ ] When should you use `raise`?
- [ ] When is returning `None` acceptable?
- [ ] Why use custom exceptions?
- [ ] What does `raise ... from ...` preserve?
- [ ] What is root cause analysis?
- [ ] How does FastAPI use `HTTPException`?
- [ ] How should Playwright jobs handle timeouts?
- [ ] How should AI backends classify LLM and tool failures?

---

# Best Practice

Production rules:

* Catch specific exceptions.
* Catch errors at the layer that can add meaning.
* Do not silently return `None` for failed operations.
* Use custom exceptions for domain errors.
* Preserve root cause with `raise ... from ...`.
* Log enough context for debugging.
* Do not leak secrets, prompts, or stack traces to users.
* Re-raise when you cannot safely recover.

---

# Common Bugs

## Bug 1: Catching Everything Too Early

```python
try:
    result = do_work()
except Exception:
    result = None
```

This hides bugs and loses root cause.

## Bug 2: Returning `None` For Invalid State

```python
def validate_prompt(prompt: str) -> bool:
    if not prompt.strip():
        return False
```

The caller may forget to check the result.

## Bug 3: Losing Root Cause

```python
try:
    call_provider()
except TimeoutError:
    raise LLMRequestError("LLM failed")
```

Prefer:

```python
try:
    call_provider()
except TimeoutError as error:
    raise LLMRequestError("LLM failed") from error
```

## Bug 4: Swallowing Playwright Failures

```python
try:
    await locator.click()
except Exception:
    pass
```

The worker now has no evidence and may continue in a broken state.

## Bug 5: Exposing Internal Errors To Users

Do not return raw traceback or provider error details to users.

---

# Code Review

A tech lead would ask:

* Is the exception specific?
* Is this the right layer to catch it?
* Does the code preserve root cause?
* Does the log include useful context?
* Does the response hide sensitive internals?
* Is cleanup guaranteed for browser, database, or network resources?
* Does the error type guide retry or user response?

Review principle:

```text
Exception handling should make failure clearer,
not quieter.
```

---

# Homework

## Mini Exercises

1. Predict `try / except` output.
2. Catch `ZeroDivisionError` precisely.
3. Trace exception propagation through three functions.
4. Implement `check_age(age)` using `raise`.
5. Implement `InvalidPromptError`.
6. Chain `TimeoutError` into `LLMRequestError`.
7. Convert `InvalidPromptError` into FastAPI `HTTPException`.
8. Design Playwright timeout handling with screenshot and cleanup.
9. Design AI backend errors for prompt validation, LLM request failure, and tool failure.

## Repository Task

- [ ] Review `docs/python/day08-exception-handling.md`.
- [ ] Review exception notes in `cheat_sheets/python.md`.
- [ ] Review Day08 interview questions in `interview/python.md`.
- [ ] Update progress tracking after review.
- [ ] Commit changes.
- [ ] Push to GitHub.
