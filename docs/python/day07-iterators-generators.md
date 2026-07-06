# Lesson 7 — Iterators & Generators

Release Badge:
🟡 Completed
Ready for Review

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 4-5 hours

Prerequisite: Day06 — Decorators

Next Lesson: Day08 — Exception Handling

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain iterable and iterator as separate concepts.
* Explain what `iter()` and `next()` do.
* Explain why Python uses `StopIteration` instead of returning `None`.
* Explain generator functions and `yield`.
* Explain `yield` vs `return`.
* Explain generator lifecycle and one-time consumption.
* Compare list comprehension and generator expression.
* Explain lazy evaluation from an engineering perspective.
* Explain `yield from`.
* Connect generators to FastAPI `StreamingResponse`, Playwright data pipelines, and
  AI backend token streaming.

---

# Why This Matters

Today is not about memorizing `iter()` and `next()`.

Today is about understanding how Python models data flow.

Tech Lead question:

When a backend system processes one million records, should it load everything first and
then start working?

Junior thought:

Maybe yes. A list is simple.

Tech Lead response:

Simple is good until the list becomes too large, too slow, or too late.

Many backend systems do not want a giant batch.

They want a stream.

Examples:

* FastAPI sends chunks to the client.
* Playwright scrapes page after page.
* An AI backend streams tokens as the model generates them.
* A data pipeline transforms records one by one.
* A log processor reads lines without loading the whole file.

That is why iterators and generators matter.

The core engineering question is:

```text
Do we need all data now,
or can we produce and consume data step by step?
```

This lesson gives the answer.

```text
Iterable / Iterator / Generator
        |
        v
Step-by-step data flow
        |
        v
Streaming, pagination, token output, pipelines
```

One classroom correction is important:

Generators are not valuable only because they save memory.

Memory is one benefit.

The deeper value is this:

```text
Generator = pausable and resumable data flow.
```

That is the mental model behind `StreamingResponse` and live AI token output.

---

# Roadmap Position

Day07 comes after decorators because the roadmap has now built the function foundation:

```text
Day01: Function objects
        |
        v
Day03: Function calls and parameter passing
        |
        v
Day05: Closures preserve state
        |
        v
Day06: Decorators wrap function behavior
        |
        v
Day07: Generators pause and resume function execution
```

The next step is exception handling.

That is not random.

Iterators use an exception, `StopIteration`, as part of normal control flow.

So Day07 prepares the student to understand why exceptions are not always just crashes.

Framework connections:

```text
Iterator protocol
        |
        +--> FastAPI StreamingResponse
        |
        +--> Playwright pagination pipelines
        |
        +--> AI token streaming
        |
        +--> Large data processing
```

---

# Lesson Map

```text
Today's Lesson

1. Iterable
2. Iterator
3. iter()
4. next()
5. StopIteration
6. Generator
7. yield vs return
8. Generator Lifecycle
9. Lazy Evaluation
10. Generator Expression
11. yield from
12. Pipeline vs Batch
13. FastAPI / Playwright / AI Streaming
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

## 1. Iterable

Tech Lead question:

What does it mean when we say a list is iterable?

Think first.

Common junior answer:

It means we can use it in a `for` loop.

That answer is useful but not deep enough.

Engineering definition:

```text
Iterable = an object that can produce an iterator.
```

Example:

```python
values = [1, 2, 3]

iterator = iter(values)
```

The list is iterable.

The object returned by `iter(values)` is the iterator.

ASCII model:

```text
Iterable
  |
  | iter()
  v
Iterator
  |
  | next()
  v
Values one by one
```

Why this design exists:

Many objects can provide data.

But not every data provider should also remember iteration position.

A list can be iterated multiple times.

Each iteration should get its own independent position.

```python
values = [1, 2, 3]

first = iter(values)
second = iter(values)

print(next(first))   # 1
print(next(first))   # 2
print(next(second))  # 1
```

This is why iterable and iterator are separated.

The list stores data.

The iterator stores traversal state.

## 2. Iterator

An iterator is the object that knows where it is during iteration.

```python
values = [10, 20, 30]
iterator = iter(values)

print(next(iterator))  # 10
print(next(iterator))  # 20
print(next(iterator))  # 30
```

Mental model:

```text
iterator over [10, 20, 30]

start
  |
  v
[10, 20, 30]
  ^
  |
current position
```

After each `next()`, the position moves forward.

```text
next() -> 10

[10, 20, 30]
      ^
      |
current position
```

Production risk:

If you pass an iterator around multiple parts of a system, each consumer changes its state.

That can create surprising bugs.

```python
items = iter([1, 2, 3])

print(next(items))  # 1

for item in items:
    print(item)     # 2, 3
```

The first item is gone because the iterator already moved.

## 3. `iter()`

`iter()` asks an object for an iterator.

```python
values = ["python", "fastapi"]
iterator = iter(values)
```

Think of `iter()` as:

```text
Please give me an object that can produce your values one by one.
```

In a `for` loop, Python does this automatically.

```python
for value in values:
    print(value)
```

is roughly:

```python
iterator = iter(values)

while True:
    try:
        value = next(iterator)
    except StopIteration:
        break

    print(value)
```

This is the hidden protocol behind `for`.

## 4. `next()`

`next()` asks the iterator for one more value.

```python
iterator = iter([1, 2])

print(next(iterator))  # 1
print(next(iterator))  # 2
```

Question:

What happens if we call `next()` again?

```python
print(next(iterator))
```

Expected answer:

`StopIteration`.

Not `None`.

Why not `None`?

Because `None` can be a valid data value.

Example:

```python
values = [1, None, 3]
iterator = iter(values)
```

If Python returned `None` to mean "finished", we could not tell whether the iterator
produced a real `None` or ended.

So Python uses a separate signal:

```text
StopIteration = the iterator is exhausted.
```

This is a design decision.

It keeps values and control flow separate.

## 5. `StopIteration`

`StopIteration` means the iterator has no more values.

```python
iterator = iter([1])

print(next(iterator))  # 1
print(next(iterator))  # raises StopIteration
```

Classroom discussion:

Is `StopIteration` an error?

Junior answer:

It looks like an error because it is an exception.

Tech Lead answer:

In the iterator protocol, it is normal control flow.

The `for` loop catches it for you.

```text
next(iterator)
      |
      +--> value
      |
      +--> StopIteration -> loop ends
```

Production thinking:

Do not treat every exception as a crash.

Some exceptions are protocol signals.

Day08 will go deeper into exception design.

## 6. Generator

A generator is a special kind of iterator created by a function that uses `yield`.

```python
def count_to_three():
    yield 1
    yield 2
    yield 3
```

Calling the function does not run the body immediately.

```python
numbers = count_to_three()
```

At this point, Python creates a generator object.

The function body starts when you call `next()`.

```python
print(next(numbers))  # 1
print(next(numbers))  # 2
print(next(numbers))  # 3
```

Mental model:

```text
generator function
        |
        | call
        v
generator object
        |
        | next()
        v
run until yield
        |
        v
pause and remember state
```

Why this matters:

The generator does not just save memory.

It pauses the function.

It remembers where it paused.

It resumes later.

That is the real model.

## 7. `yield`

`yield` produces a value and pauses the function.

```python
def workflow():
    print("start")
    yield "first"
    print("middle")
    yield "second"
    print("end")
```

Output prediction:

```python
gen = workflow()

print(next(gen))
print(next(gen))
```

Expected output:

```text
start
first
middle
second
```

The line `print("end")` has not run yet.

It runs only when the generator resumes again and reaches the end.

## 8. `yield` vs `return`

`return` ends a function.

`yield` pauses a function and produces a value.

```text
return
  |
  v
function ends

yield
  |
  v
value produced
function state preserved
function can resume
```

Example:

```python
def make_list():
    return [1, 2, 3]


def make_generator():
    yield 1
    yield 2
    yield 3
```

`make_list()` creates all values now.

`make_generator()` produces values one by one.

## 9. Generator Lifecycle

A generator has a lifecycle.

```text
Created
  |
  v
Running
  |
  v
Paused at yield
  |
  v
Running again
  |
  v
Exhausted
```

Example:

```python
def numbers():
    yield 1
    yield 2


gen = numbers()

print(next(gen))  # 1
print(next(gen))  # 2
print(next(gen))  # StopIteration
```

After a generator is exhausted, it is done.

It does not restart.

## 10. Generator Can Only Be Consumed Once

This is a major classroom point.

```python
def numbers():
    yield 1
    yield 2


gen = numbers()

print(list(gen))  # [1, 2]
print(list(gen))  # []
```

Why?

Because the generator is the iterator.

It carries its own traversal state.

After it reaches the end, it is exhausted.

If you need to iterate again, create a new generator:

```python
print(list(numbers()))  # [1, 2]
print(list(numbers()))  # [1, 2]
```

Production risk:

Logging or debugging can accidentally consume a generator.

```python
rows = load_rows()
print(list(rows))  # consumes everything

for row in rows:
    process(row)   # nothing left
```

Tech Lead review:

If a value is a generator, be careful before converting it to a list for debugging.

## 11. Lazy Evaluation

Lazy evaluation means work happens only when values are requested.

```python
def read_rows():
    print("read row 1")
    yield {"id": 1}
    print("read row 2")
    yield {"id": 2}
```

Calling `read_rows()` does not read rows.

`next()` triggers work.

This matters in production because lazy pipelines can start producing useful output before
all data is ready.

```text
Batch:
load all -> transform all -> return all

Pipeline:
load one -> transform one -> return one
load next -> transform next -> return next
```

The generator value is not only memory saving.

It is time-to-first-result.

## 12. Generator Expression

List comprehension:

```python
squares = [x * x for x in range(3)]
```

Generator expression:

```python
squares = (x * x for x in range(3))
```

Difference:

```text
List comprehension:
build all values immediately

Generator expression:
produce values lazily
```

Example:

```python
values = (x * 2 for x in range(3))

print(next(values))  # 0
print(next(values))  # 2
print(next(values))  # 4
```

Engineering decision:

Use a list when you need:

* repeated iteration
* indexing
* length
* all results now

Use a generator when you need:

* streaming
* one-pass processing
* lazy transformation
* large or unbounded data

## 13. `yield from`

`yield from` delegates yielding to another iterable.

```python
def numbers():
    yield from [1, 2, 3]
```

Equivalent:

```python
def numbers():
    for value in [1, 2, 3]:
        yield value
```

Why it matters:

It helps compose generators.

```python
def section_one():
    yield "a"
    yield "b"


def section_two():
    yield "c"


def all_sections():
    yield from section_one()
    yield from section_two()
```

Pipeline model:

```text
section_one -> yields a, b
section_two -> yields c
all_sections -> streams a, b, c
```

## 14. Pipeline vs Batch

Batch processing:

```python
def load_all_pages() -> list[str]:
    return ["page1", "page2", "page3"]
```

Pipeline processing:

```python
def load_pages():
    yield "page1"
    yield "page2"
    yield "page3"
```

Batch waits for everything.

Pipeline moves one item at a time.

Engineering comparison:

| Design | Strength | Risk |
|--------|----------|------|
| Batch | Simple, reusable list | High memory, slower first output |
| Pipeline | Streaming, lower memory, faster first output | One-time consumption, harder debugging |

Backend systems often choose pipeline design when:

* input is large
* output can be streamed
* latency matters
* data source is paginated
* downstream system can process incrementally

---

# Engineering Thinking

The question behind Day07 is:

```text
Who owns the flow of data?
```

A list says:

```text
Here is everything.
```

A generator says:

```text
Ask me for the next value when you are ready.
```

This is a major backend design difference.

## Why Iterable and Iterator Are Separated

If an iterable and iterator were always the same object, repeated loops would be dangerous.

```python
values = [1, 2, 3]

for value in values:
    ...

for value in values:
    ...
```

Lists can support this safely because each `for` loop gets a new iterator.

Separation gives Python:

* reusable data containers
* independent traversal state
* clean `for` loop behavior
* support for one-pass streams

## Why `StopIteration` Does Not Return `None`

`None` is data.

`StopIteration` is control flow.

If Python used `None` to mean done, iterators could not safely produce real `None` values.

The design keeps the protocol unambiguous.

## Why Generator Value Is Data Flow, Not Only Memory

A generator is a paused function.

It keeps:

* local variables
* current execution position
* pending work
* ability to resume

That makes it useful for:

* API streaming
* LLM token streaming
* file processing
* browser scraping pipelines
* data transformation chains

## Production Risks

Generators are powerful, but they introduce risks:

* A generator can be consumed only once.
* Debugging with `list(generator)` can consume it.
* Exceptions may happen later than expected.
* Resource cleanup must be handled carefully.
* Streaming can expose partial results before the full operation completes.
* Long-lived generators can hold references longer than expected.

Tech Lead review question:

```text
Is this data flow one-pass, or does the caller expect reusable data?
```

If the caller expects reuse, return a list.

If the caller expects streaming, return a generator.

---

# Classroom Exercises

## Exercise 1: Iterable vs Iterator

Starter Code:

```python
values = [1, 2, 3]
iterator = iter(values)
```

Think First:

Which object is iterable? Which object is the iterator?

Expected Answer:

`values` is iterable. `iterator` is the iterator returned by `iter(values)`.

Explanation:

The list stores data. The iterator stores traversal position.

Follow-up Question:

Can the same list create two independent iterators?

## Exercise 2: `next()` Output Prediction

Starter Code:

```python
iterator = iter(["a", "b"])

print(next(iterator))
print(next(iterator))
print(next(iterator))
```

Think First:

What happens on the third `next()`?

Expected Output:

```text
a
b
StopIteration
```

Explanation:

The iterator has no third value, so it signals exhaustion with `StopIteration`.

Follow-up Question:

Why does Python not return `None`?

## Exercise 3: For Loop Translation

Starter Code:

```python
for item in [10, 20]:
    print(item)
```

Think First:

What hidden protocol does Python use?

Expected Answer:

Python calls `iter()` to get an iterator, then repeatedly calls `next()` until
`StopIteration`.

Explanation:

The `for` loop is syntax around the iterator protocol.

Follow-up Question:

Where is `StopIteration` handled?

## Exercise 4: Generator Lifecycle

Starter Code:

```python
def workflow():
    print("start")
    yield 1
    print("middle")
    yield 2
    print("end")


gen = workflow()
print(next(gen))
print(next(gen))
```

Think First:

Does `print("end")` run?

Expected Output:

```text
start
1
middle
2
```

Explanation:

The generator pauses after `yield 2`. It has not resumed to the final `print("end")`.

Follow-up Question:

What happens if you call `next(gen)` one more time?

## Exercise 5: Generator Can Only Be Consumed Once

Starter Code:

```python
def numbers():
    yield 1
    yield 2


gen = numbers()
print(list(gen))
print(list(gen))
```

Think First:

Why is the second list empty?

Expected Output:

```text
[1, 2]
[]
```

Explanation:

The generator was exhausted by the first `list(gen)` call.

Follow-up Question:

How do you get the values again?

## Exercise 6: Generator Expression

Starter Code:

```python
values = (x * 10 for x in range(3))

print(next(values))
print(next(values))
```

Think First:

Are all values computed immediately?

Expected Output:

```text
0
10
```

Explanation:

The generator expression computes values lazily.

Follow-up Question:

When would a list comprehension be better?

## Exercise 7: `yield from`

Starter Code:

```python
def one():
    yield "a"
    yield "b"


def two():
    yield from one()
    yield "c"


print(list(two()))
```

Think First:

What does `yield from one()` do?

Expected Output:

```text
['a', 'b', 'c']
```

Explanation:

`yield from` delegates yielding to another iterable.

Follow-up Question:

How would you write the same logic with a `for` loop?

## Exercise 8: FastAPI StreamingResponse Thinking

Starter Code:

```python
def stream_lines():
    yield "line 1\n"
    yield "line 2\n"
```

Think First:

Why is a generator useful for HTTP streaming?

Expected Answer:

The server can send chunks as they are produced instead of waiting for the whole response.

Explanation:

This improves time-to-first-byte and avoids building the entire response in memory.

Follow-up Question:

What production risks exist in streaming responses?

## Exercise 9: Playwright Data Pipeline

Starter Code:

```python
def scrape_pages(pages):
    for page in pages:
        yield {"page": page}
```

Think First:

Is this batch or pipeline design?

Expected Answer:

Pipeline design.

Explanation:

Each page result can be processed as soon as it is scraped.

Follow-up Question:

Why might this be better than collecting all pages first?

## Exercise 10: AI Token Streaming

Starter Code:

```python
def fake_tokens():
    yield "Hel"
    yield "lo"
    yield "!"
```

Think First:

Why does this feel like ChatGPT streaming output?

Expected Answer:

Each token chunk is produced incrementally instead of waiting for the full message.

Explanation:

Token streaming is a data-flow model: produce, send, resume.

Follow-up Question:

What should an AI backend track while streaming?

---

# FastAPI Connections

FastAPI uses generators for streaming responses.

Example:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


def stream_numbers():
    for number in range(3):
        yield f"{number}\n"


@app.get("/numbers")
def numbers():
    return StreamingResponse(stream_numbers(), media_type="text/plain")
```

Why use a generator?

Because the response can be produced in chunks.

```text
client connects
        |
        v
yield chunk 1 -> send chunk 1
        |
        v
yield chunk 2 -> send chunk 2
        |
        v
yield chunk 3 -> send chunk 3
```

This is not just about memory.

It is about streaming behavior.

The client can start receiving data before the server has produced everything.

Production risks:

* The generator may fail midway.
* Resource cleanup must be clear.
* Client disconnects must be handled.
* Streaming should not expose partial sensitive data.
* Logging should not consume the generator accidentally.

AI Backend connection:

FastAPI can stream LLM token chunks to the frontend using the same mental model.

---

# Playwright Connections

Playwright automation often produces data page by page.

Batch design:

```python
async def scrape_all(pages):
    results = []

    for page in pages:
        results.append(await scrape_page(page))

    return results
```

Pipeline thinking:

```python
async def scrape_pipeline(pages):
    for page in pages:
        yield await scrape_page(page)
```

The pipeline version lets downstream code process results earlier.

Why this matters:

* long scraping jobs can stream progress
* partial results can be saved
* memory usage stays bounded
* failures can be isolated by page
* workers can process page results incrementally

Production risks:

* Async generators need careful error handling.
* Browser contexts must be closed reliably.
* Retrying a page should not duplicate saved results.
* A consumed generator cannot be replayed unless the scrape is run again.

AI Backend connection:

An AI agent that uses Playwright can stream scraped observations into an analysis pipeline
instead of waiting for every page to finish.

---

# English Interview

## Key Vocabulary

* iterable
* iterator
* iterator protocol
* `iter()`
* `next()`
* `StopIteration`
* generator
* `yield`
* lazy evaluation
* generator expression
* `yield from`
* pipeline processing
* streaming response

## Beginner Questions

### What is an iterable?

Standard Answer:

An iterable is an object that can produce an iterator, usually by being passed to `iter()`.

Follow-up Questions:

* Is a list iterable?
* Can one iterable create multiple iterators?

Engineering Perspective:

Iterables represent data sources that can be traversed. In backend code, they are useful
because many systems expose data as sequences, pages, rows, or chunks.

### What is an iterator?

Standard Answer:

An iterator is an object that produces values one at a time with `next()` and remembers
its current position.

Follow-up Questions:

* What happens when an iterator is exhausted?
* Can an iterator usually be reused?

Engineering Perspective:

Iterators carry traversal state, so sharing one iterator across consumers can create
surprising state bugs.

### What does `iter()` do?

Standard Answer:

`iter()` asks an iterable for an iterator.

Follow-up Questions:

* What does a `for` loop do internally?
* What happens if an object is not iterable?

Engineering Perspective:

`iter()` is the entry point to Python's iteration protocol.

### What does `next()` do?

Standard Answer:

`next()` asks an iterator for the next value.

Follow-up Questions:

* What happens when there are no more values?
* Why does `next()` not return `None` at the end?

Engineering Perspective:

`next()` is pull-based data flow: the consumer asks for one more item when ready.

### What is `StopIteration`?

Standard Answer:

`StopIteration` is the signal that an iterator has no more values.

Follow-up Questions:

* Is `StopIteration` always a bug?
* Who catches `StopIteration` in a `for` loop?

Engineering Perspective:

In the iterator protocol, `StopIteration` is normal control flow, not a crash.

### What is a generator?

Standard Answer:

A generator is an iterator created by a function that uses `yield`.

Follow-up Questions:

* Does calling a generator function run its body immediately?
* What does `yield` do?

Engineering Perspective:

Generators model pausable and resumable data flow, which is why they fit streaming systems.

### What is the difference between `yield` and `return`?

Standard Answer:

`return` ends a function. `yield` produces a value and pauses the function so it can resume
later.

Follow-up Questions:

* Can a generator yield multiple values?
* What happens when a generator reaches the end?

Engineering Perspective:

`yield` is useful when a system should produce values incrementally instead of all at once.

## Intermediate Questions

### Why are iterable and iterator separated?

Standard Answer:

They are separated so data containers can be reusable while iterator objects hold traversal
state.

Follow-up Questions:

* Why can a list be looped over multiple times?
* Why is a generator usually one-time use?

Engineering Perspective:

Separation prevents traversal state from being stored directly on reusable containers.

### Why does Python use `StopIteration` instead of returning `None`?

Standard Answer:

Because `None` can be a valid value. `StopIteration` clearly separates end-of-iteration
control flow from actual data.

Follow-up Questions:

* Can an iterator yield `None`?
* What would break if `None` meant finished?

Engineering Perspective:

The protocol avoids ambiguous data signals.

### Why can a generator only be consumed once?

Standard Answer:

A generator is its own iterator and stores its current execution state. Once it reaches the
end, it is exhausted.

Follow-up Questions:

* How do you iterate again?
* What production bug can happen when logging a generator?

Engineering Perspective:

Generators are one-pass streams. Treat them like streams, not reusable lists.

### Generator Expression vs List Comprehension

Standard Answer:

A list comprehension builds a list immediately. A generator expression produces values
lazily as they are requested.

Follow-up Questions:

* Which one supports indexing?
* Which one is better for streaming?

Engineering Perspective:

Choose a list when you need reuse and random access. Choose a generator when you need
one-pass lazy processing.

### What is lazy evaluation?

Standard Answer:

Lazy evaluation means computation happens only when a value is requested.

Follow-up Questions:

* How does lazy evaluation affect memory?
* How does it affect time-to-first-result?

Engineering Perspective:

Lazy evaluation improves streaming and pipeline behavior, not only memory usage.

## Senior Questions

### Explain Python Generator Protocol.

Standard Answer:

A generator follows the iterator protocol. It returns a generator object, produces values
with `yield`, resumes on `next()`, and signals completion with `StopIteration`.

Follow-up Questions:

* What state does a generator preserve?
* How does a `for` loop consume a generator?

Engineering Perspective:

The protocol gives Python a uniform way to consume lists, files, streams, and generated
data.

### Explain Generator Lifecycle.

Standard Answer:

A generator is created, starts running when consumed, pauses at each `yield`, resumes on
the next request, and eventually becomes exhausted.

Follow-up Questions:

* Does calling the generator function run the body?
* What happens after exhaustion?

Engineering Perspective:

The lifecycle matters for resource management and streaming error handling.

### Why does FastAPI `StreamingResponse` use generators?

Standard Answer:

`StreamingResponse` can consume a generator and send chunks as they are produced instead
of building the entire response first.

Follow-up Questions:

* What happens if the generator fails midway?
* Why is this useful for large responses?

Engineering Perspective:

Generators improve time-to-first-byte and support streaming APIs.

### Explain generator-based streaming in AI Backend.

Standard Answer:

An AI backend can yield token chunks as the model produces them, allowing the client to
display output incrementally.

Follow-up Questions:

* Why does ChatGPT appear to type in real time?
* What should be tracked during token streaming?

Engineering Perspective:

Token streaming is a pausable data-flow model. It improves perceived latency and user
experience.

### Explain Pipeline vs Batch processing.

Standard Answer:

Batch processing collects all data before processing or returning it. Pipeline processing
passes each item through stages as it becomes available.

Follow-up Questions:

* Which design has faster first output?
* Which design is easier to debug?

Engineering Perspective:

Pipeline design scales better for large or streaming data, but it requires careful handling
of one-time consumption and partial failures.

### How does generator design improve scalability?

Standard Answer:

Generators improve scalability by producing data incrementally, reducing peak memory use,
supporting streaming output, and enabling pipeline processing.

Follow-up Questions:

* Is memory saving the only benefit?
* What risks come with generator-based design?

Engineering Perspective:

The deeper scalability benefit is controlled data flow: the system can process one item or
chunk at a time.

---

# Today's Takeaway

Iterator and generator thinking is data-flow thinking.

The basic tools:

```text
iterable -> iter() -> iterator -> next() -> value
```

The end signal:

```text
StopIteration
```

The generator model:

```text
yield value
pause
resume later
```

The engineering lesson:

```text
Generators are not just memory-saving tools.
They are pausable, resumable, one-pass data streams.
```

FastAPI uses this model for `StreamingResponse`.

Playwright pipelines use this model for page-by-page data flow.

AI backends use this model for token streaming.

---

# Before Next Lesson Checklist

Before Day08, confirm you can answer these without notes:

- [ ] What is an iterable?
- [ ] What is an iterator?
- [ ] What does `iter()` do?
- [ ] What does `next()` do?
- [ ] Why does Python use `StopIteration` instead of `None`?
- [ ] Why are iterable and iterator separated?
- [ ] What is a generator?
- [ ] What does `yield` do?
- [ ] What is the difference between `yield` and `return`?
- [ ] What is generator lifecycle?
- [ ] Why can a generator only be consumed once?
- [ ] What is lazy evaluation?
- [ ] When should you use a generator expression?
- [ ] What does `yield from` do?
- [ ] Why does FastAPI `StreamingResponse` use generators?
- [ ] Why can ChatGPT stream tokens in real time?

---

# Best Practice

Use a list when:

* you need repeated iteration
* you need indexing
* you need `len()`
* the data is small and simple
* callers expect reusable data

Use a generator when:

* the data is large
* the data is produced over time
* you need streaming
* you need one-pass processing
* you want faster time-to-first-result

Production rules:

* Do not accidentally consume generators during logging.
* Do not assume a generator can be reused.
* Be explicit about ownership of streaming data.
* Handle cleanup for file, network, browser, and database resources.
* Prefer clear names such as `iter_rows`, `stream_events`, or `generate_tokens`.

---

# Common Bugs

## Bug 1: Expecting A Generator To Restart

```python
gen = (x for x in range(3))

print(list(gen))  # [0, 1, 2]
print(list(gen))  # []
```

The generator is exhausted after the first consumption.

## Bug 2: Treating `StopIteration` As A Crash

`StopIteration` is normal iterator protocol control flow.

## Bug 3: Debugging By Consuming

```python
rows = load_rows()
logger.info("rows=%s", list(rows))
```

This consumes the generator.

## Bug 4: Choosing Generator When Caller Needs Reuse

If the caller needs length, indexing, or repeated loops, a list may be a better contract.

## Bug 5: Forgetting Streaming Failures

A streaming response can fail after the client has already received partial data.

---

# Code Review

A tech lead would ask:

* Is this data supposed to be reusable or one-pass?
* Is the generator consumed exactly once?
* Could logging or debugging accidentally consume it?
* Are resource lifetimes clear?
* Are exceptions handled at the right level?
* Is pipeline processing worth the added complexity?
* Does the API contract say list, iterable, iterator, or generator?

Review principle:

```text
Use generators when streaming behavior is part of the design,
not just because generators look clever.
```

---

# Homework

## Mini Exercises

1. Classify objects as iterable, iterator, or both.
2. Translate a `for` loop into `iter()` and `next()`.
3. Explain why `StopIteration` is not `None`.
4. Predict generator output order.
5. Draw generator lifecycle from memory.
6. Demonstrate one-time generator consumption.
7. Compare list comprehension and generator expression.
8. Rewrite nested generators using `yield from`.
9. Design a FastAPI streaming response.
10. Design a Playwright page pipeline.
11. Explain AI token streaming using generator language.

## Repository Task

- [ ] Review `docs/python/day07-iterators-generators.md`.
- [ ] Review iterator/generator notes in `cheat_sheets/python.md`.
- [ ] Review Day07 interview questions in `interview/python.md`.
- [ ] Update progress tracking after review.
- [ ] Commit changes.
- [ ] Push to GitHub.
