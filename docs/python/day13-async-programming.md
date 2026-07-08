# Lesson 13 — Async Programming

Release Badge:
🟢 Completed

Version: v1.0

Status: Completed

Difficulty: Foundation

Estimated Time: 5-6 hours

Prerequisite: Day12 — Context Managers

Next Lesson: Day14 — Mini Project + Mock Interview

---

## Learning Objectives

After completing this lesson, the student should be able to:

* Explain that async improves I/O throughput, not CPU speed.
* Explain blocking vs non-blocking from the Event Loop's perspective.
* Explain the Event Loop as a single-thread cooperative scheduler.
* Explain coroutine, coroutine object, Task, and the difference between them.
* Explain what `await` does to the current Task and to the Event Loop.
* Explain `asyncio.gather()` concurrency and why results keep input order.
* Explain the Task lifecycle and cooperative cancellation.
* Explain exception propagation and "Task exception was never retrieved".
* Explain why a `Semaphore` protects downstream capacity.
* Connect async to FastAPI, Playwright, and AI backend concurrency.
* Answer beginner, intermediate, and senior interview questions.

---

# Why This Matters

Async is not about making Python "faster".

Async is about not wasting the CPU while the program waits for I/O.

Tech Lead Question:

When your backend calls OpenAI, Redis, and PostgreSQL, where does the time actually go?

Think first.

Student Answer:

"Most of the time is spent waiting for the network and the database, not computing."

Tech Lead Correction:

Correct, and that is the whole point.

```text
I/O Bound work
      |
      v
CPU is idle, just waiting
      |
      v
Async lets the CPU run other Tasks while waiting
```

Async improves **throughput for I/O-bound work**.

It does not make CPU-bound work faster. A single-threaded Event Loop still runs one line of
Python at a time.

The production motivation comes before the syntax:

```text
One request is waiting on OpenAI (2 seconds).
Without async: the worker is blocked, other requests wait.
With async: the Event Loop serves other requests during those 2 seconds.
```

So the mental model for Day13 is not "how do I write `async def`".

The mental model is:

```text
What is the Event Loop doing?
Which Task is running?
Which Task is suspended?
Why is the scheduler switching?
```

If you keep asking those questions, async stops being magic.

---

# Roadmap Position

Day07 taught generators: pause and resume.

Day12 taught context managers: deterministic cleanup.

Day13 combines both ideas into cooperative scheduling.

```text
Day07: Generators (pause / resume)
        |
        v
Day12: Context Managers (cleanup guarantee)
        |
        v
Day13: Async Programming (Event Loop scheduling)
        |
        v
Day14: Mini Project + Mock Interview
        |
        v
FastAPI async endpoints
        |
        v
Playwright async automation
        |
        v
AI backend concurrency control
```

A coroutine is a pausable and resumable unit of work, just like a generator.

The Event Loop is the scheduler that decides which paused work resumes next.

```text
Pausable work (coroutine)
        +
Scheduler (event loop)
        |
        v
Concurrency without threads
```

This is why Day13 sits right before the mini project: real backends are async.

---

# Lesson Map

```text
Today's Lesson

1. Why Async Matters (I/O throughput)
2. I/O Bound vs CPU Bound
3. Blocking vs Non-blocking
4. The Event Loop
5. Coroutine and Coroutine Object
6. Task vs Coroutine
7. await
8. asyncio.gather()
9. Task Lifecycle
10. Task Cancellation
11. Exception Propagation
12. Semaphore and Concurrency Control
13. FastAPI, Playwright, and AI Backend Connections
14. Interview Review
```

---

# Estimated Study Time

```text
Reading: 120-150 minutes
Exercises: 60-90 minutes
Coding: 60-90 minutes
Review: 30-45 minutes

Total: 5-6 hours
```

---

# Main Concepts

## Concept 1: I/O Bound vs CPU Bound

Async only helps one of these two categories.

```text
I/O Bound  -> waiting on network, disk, database, API
CPU Bound  -> computing, parsing, math, encoding
```

Tech Lead Question:

Would async speed up resizing 10,000 images?

Think first.

Student Answer:

"No. That is CPU work. The CPU is busy, not waiting."

Tech Lead Correction:

Exactly.

```text
I/O Bound -> CPU waits -> async helps
CPU Bound -> CPU works -> async does not help
```

For CPU-bound work you need processes or threads, not the Event Loop.

Backend motivation:

Most backend latency is I/O: calling OpenAI, querying PostgreSQL, reading Redis. That is
exactly where async pays off.

## Concept 2: Blocking vs Non-blocking

This is the most important distinction of the day.

```python
import time
import asyncio


def blocking():
    time.sleep(2)        # blocks the whole Event Loop


async def non_blocking():
    await asyncio.sleep(2)   # suspends only this Task
```

Event Loop view:

```text
time.sleep(2)
   |
   v
Event Loop is frozen for 2 seconds
   |
   v
No other Task can run

asyncio.sleep(2)
   |
   v
This Task suspends
   |
   v
Event Loop runs other Tasks
   |
   v
This Task resumes after 2 seconds
```

Tech Lead Question:

During `time.sleep(2)` inside an `async def`, which Task can run?

Think first.

Student Answer:

"None. `time.sleep` blocks the single thread, so the Event Loop cannot switch."

Tech Lead Correction:

Correct, and this is a real production incident pattern.

Production Risk:

```text
A blocking call inside async def freezes every concurrent request on that worker.
```

Rule:

```text
Never call a blocking function inside async code.
Use the async version, or push it to a thread with asyncio.to_thread().
```

## Concept 3: The Event Loop

The Event Loop is a single thread that schedules Tasks cooperatively.

```text
                 +------------------+
   Ready Queue -> |   Event Loop     | -> runs one Task at a time
                 +------------------+
                        |  ^
             await (suspend)  |  ready (resume)
                        v  |
                 +------------------+
                 |  Waiting State   |  (I/O not finished yet)
                 +------------------+
```

Key properties:

```text
Single Thread    -> one line of Python runs at a time
Ready Queue      -> Tasks that can run now
Waiting State    -> Tasks waiting on I/O
Suspend          -> a Task yields control at await
Resume           -> the loop continues a Task when its I/O is ready
```

Tech Lead Question:

If there is only one thread, how can we have concurrency?

Think first.

Student Answer:

"Because Tasks give up control while waiting, so the single thread stays busy with other
Tasks instead of blocking."

Tech Lead Correction:

Exactly.

This is **cooperative scheduling**. A Task keeps running until it hits an `await`, then it
voluntarily releases the Event Loop.

```text
Concurrency = overlapping waiting, not parallel CPU work
```

## Concept 4: Coroutine and Coroutine Object

`async def` defines a coroutine function.

Calling it does **not** run the code.

```python
async def hello():
    print("hi")


coro = hello()   # nothing prints yet
print(coro)      # <coroutine object hello at 0x...>
```

Coroutine lifecycle:

```text
async def hello         -> defines a coroutine function
hello()                 -> creates a coroutine object (an execution plan)
                        -> NOT executed yet
await hello() / Task    -> hands the plan to the Event Loop
Event Loop              -> actually runs it
```

Tech Lead Question:

Why does calling `hello()` not print anything?

Think first.

Student Answer:

"Because `hello()` only builds a coroutine object. It is a plan, not a running function."

Tech Lead Correction:

Correct.

A coroutine object is an **execution plan** the Event Loop can run later.

Common Mistake:

```python
hello()   # RuntimeWarning: coroutine 'hello' was never awaited
```

Creating a coroutine without awaiting or scheduling it does nothing useful and warns.

## Concept 5: Task vs Coroutine

A coroutine is a plan.

A Task is a coroutine that the Event Loop is actively driving.

```text
Coroutine
   |
   v
wrap with asyncio.create_task()
   |
   v
Task
   |
   v
Event Loop
   |
   v
Running (scheduled concurrently)
```

```python
async def main():
    task = asyncio.create_task(hello())   # scheduled now, runs concurrently
    await task                            # wait for its result
```

Tech Lead Question:

What is the difference between `await hello()` and `asyncio.create_task(hello())`?

Think first.

Student Answer:

"`await hello()` runs it and waits right here. `create_task` schedules it to run
concurrently and lets me await later."

Tech Lead Correction:

Exactly.

```text
await coro()          -> run now, block here until done
create_task(coro())   -> schedule now, run concurrently, await later
```

A Task is what enables real concurrency, because it starts running while you do other work.

## Concept 6: `await`

`await` suspends the current coroutine and releases the Event Loop.

```text
await something
   |
   v
current coroutine suspends
   |
   v
Event Loop is released to run other Tasks
   |
   v
when the awaited work is ready, this coroutine resumes
```

Three facts to memorize:

```text
await suspends the current coroutine.
await does NOT create a thread.
await releases the Event Loop so other Tasks run.
```

Tech Lead Question:

Does `await` make the code run in parallel on multiple cores?

Think first.

Student Answer:

"No. It is still one thread. `await` just lets the loop switch to another Task while this one
waits."

Tech Lead Correction:

Correct.

`await` is a suspension point, not a thread spawner.

## Concept 7: `asyncio.gather()`

`gather()` runs multiple coroutines concurrently and collects their results.

```python
results = await asyncio.gather(
    fetch_user(),
    fetch_orders(),
    fetch_recommendations(),
)
```

Sequential vs concurrent:

```python
# Sequential: total time = t1 + t2
a = await task1()
b = await task2()

# Concurrent: total time = max(t1, t2)
a, b = await asyncio.gather(task1(), task2())
```

Event Loop view:

```text
gather starts all coroutines
   |
   v
each awaits its I/O and suspends
   |
   v
Event Loop overlaps their waiting
   |
   v
gather returns when all are done
```

Tech Lead Question:

If `task2` finishes before `task1`, will `gather` return them out of order?

Think first.

Student Answer:

"No. `gather` returns results in the order I passed the coroutines, regardless of which
finished first."

Tech Lead Correction:

Exactly.

```text
Completion order != return order
gather preserves INPUT order in the results list
```

This is why `a, b = await asyncio.gather(task1(), task2())` is safe: `a` is always `task1`'s
result even if `task2` completed first.

## Concept 8: Task Lifecycle

```text
Pending
   |
   v
Running  <----+
   |          |
 await        | resume
   v          |
Suspend ------+
   |
   v
Done  ----> result or exception stored

(any point) --> Cancelled --> CancelledError
```

States:

```text
Pending   -> created, not started
Running   -> currently executing on the loop
Suspend   -> paused at an await
Resume    -> continued by the loop when ready
Done       -> finished with a result or an exception
Cancelled  -> cancellation requested, CancelledError raised inside
```

Tech Lead Question:

When a Task is "Suspend", is it using the CPU?

Think first.

Student Answer:

"No. It is parked in the waiting state. The CPU is free for other Tasks."

Tech Lead Correction:

Correct. Suspended Tasks cost memory, not CPU.

## Concept 9: Task Cancellation

Cancellation is **cooperative**, not an instant kill.

```python
task = asyncio.create_task(long_job())
task.cancel()             # request cancellation, not immediate stop
```

What actually happens:

```text
task.cancel()
   |
   v
a CancellationRequest is scheduled
   |
   v
at the next await, CancelledError is raised INSIDE the task
   |
   v
finally / cleanup runs
   |
   v
CancelledError propagates
```

```python
async def long_job():
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # cleanup: close connections, release resources
        raise            # re-raise so cancellation completes
```

Tech Lead Question:

Why is `task.cancel()` not an immediate kill?

Think first.

Student Answer:

"Because the loop is single-threaded and cooperative. It can only inject `CancelledError`
when the Task reaches an await."

Tech Lead Correction:

Exactly.

Rules:

```text
cancel() requests cancellation.
CancelledError is raised at the next suspension point.
Run cleanup in except/finally.
Usually re-raise CancelledError so cancellation is honored.
```

Framework Connection:

FastAPI cancels a request Task when the client disconnects. Playwright cancellation stops a
navigation or click that is awaiting.

## Concept 10: Exception Propagation

A Task stores its exception until you `await` it.

```python
task = asyncio.create_task(might_fail())
# exception is stored, not raised yet
await task   # re-raises the stored exception here
```

Event Loop view:

```text
Task raises inside
   |
   v
exception stored on the Task object
   |
   v
await task  -> exception re-raised to the awaiter
```

Tech Lead Question:

What happens if you never await a failing Task?

Think first.

Student Answer:

"The exception is never retrieved, so asyncio warns: 'Task exception was never retrieved'."

Tech Lead Correction:

Correct.

```text
await task        -> you see and handle the error
fire-and-forget   -> error may be silently lost, then warned at GC
```

Difference:

```text
await task           -> synchronous-style error handling with try/except
create_task + forget -> must attach a done callback or you lose the error
```

Production Risk:

Fire-and-forget Tasks that fail silently hide real backend errors.

## Concept 11: Semaphore

Unlimited `gather()` is dangerous.

```python
# DANGER: 10,000 concurrent OpenAI calls
await asyncio.gather(*[call_openai(p) for p in prompts])
```

A `Semaphore` limits how many Tasks run the protected section at once.

```python
sem = asyncio.Semaphore(10)   # at most 10 concurrent

async def limited_call(prompt):
    async with sem:
        return await call_openai(prompt)

await asyncio.gather(*[limited_call(p) for p in prompts])
```

Semaphore view:

```text
                 +-------------------+
   Many Tasks -> |  Semaphore(10)    | -> only 10 pass at a time
                 +-------------------+
                    | | | | | | | | | |
                    v v v v v v v v v v
                  10 concurrent downstream calls
                    |
                    v
             the rest wait for a slot
```

Tech Lead Question:

Why is limiting concurrency sometimes faster and more reliable than unlimited concurrency?

Think first.

Student Answer:

"Because downstream services have limits. Too many concurrent calls cause rate limits,
timeouts, and connection exhaustion, which makes everything slower."

Tech Lead Correction:

Exactly.

```text
Unlimited concurrency -> overload -> 429s, timeouts, pool exhaustion
Bounded concurrency   -> stable throughput -> predictable latency
```

Downstream capacity you must respect:

```text
OpenAI API   -> rate limits (HTTP 429)
Redis        -> connection limits
PostgreSQL   -> connection pool size
GPU          -> memory and batch limits
Browser      -> memory per context
```

The goal is **stable throughput**, not maximum concurrency.

---

# Engineering Thinking

## Why the Event Loop Uses Cooperative Scheduling

If I were designing the Event Loop, why cooperative instead of preemptive?

```text
Cooperative:
- single thread, no locks for most app state
- switches only at await, so state is predictable
- cheap context switches
```

The trade-off:

```text
One blocking call freezes everything.
```

That is the price of a simple, fast, lock-light model.

## Why Cancellation Is Cooperative

The loop cannot forcibly stop code between `await` points, because it only regains control at
suspension points.

```text
No await -> no place to inject CancelledError
```

So long CPU sections are both un-cancellable and loop-blocking. Another reason to keep CPU
work out of the loop.

## Why `gather()` Returns Input Order

Because backend code indexes results positionally.

```text
user, orders = await gather(fetch_user(), fetch_orders())
```

If order followed completion time, this unpacking would be a race condition. Input order makes
concurrency safe to reason about.

## Why Concurrency Is Not Always Better

More concurrency increases pressure on downstream systems and memory.

```text
Stable Throughput  -> bounded concurrency, predictable, resilient
Maximum Concurrency -> bursty, overload-prone, unpredictable
```

A senior engineer optimizes for stable throughput.

## Tech Lead Review Checklist

* Is any blocking call hiding inside `async def`?
* Is `to_thread()` used for unavoidable blocking work?
* Is `gather()` bounded by a `Semaphore` for external calls?
* Are Tasks awaited, or fire-and-forget with lost exceptions?
* Is cancellation handled with cleanup and re-raise?
* Does the code respect downstream rate limits and pool sizes?

## CTO Thinking

```text
Reliability  -> bounded concurrency survives load spikes
Cost         -> fewer 429 retries and wasted tokens
Scalability  -> one worker serves many I/O-bound requests
Stability    -> no single blocking call taking down a worker
```

---

# Classroom Exercises

## Level 1: Blocking vs Non-blocking

Question:

Which version lets other Tasks run during the wait?

Think First:

Which call freezes the single thread?

Starter Code:

```python
import time, asyncio

async def a():
    time.sleep(1)

async def b():
    await asyncio.sleep(1)
```

Expected Output:

`b` is non-blocking; `a` blocks the Event Loop for one second.

Explanation:

`time.sleep` blocks the thread. `asyncio.sleep` suspends only the current Task.

Follow-up Question:

How would you make `a` safe without removing the blocking call?

## Level 2: Coroutine

Question:

What does `hello()` return, and does it run?

Think First:

Does `async def` run when called?

Starter Code:

```python
async def hello():
    print("hi")

x = hello()
print(x)
```

Expected Output:

```text
<coroutine object hello at 0x...>
```

Explanation:

Calling a coroutine function builds a coroutine object; it does not execute the body.

Follow-up Question:

What warning appears if `x` is never awaited?

## Level 3: Task

Question:

Make two coroutines run concurrently.

Think First:

What turns a coroutine into concurrently running work?

Starter Code:

```python
async def main():
    ...
```

Expected Output:

```python
async def main():
    t1 = asyncio.create_task(job("a"))
    t2 = asyncio.create_task(job("b"))
    await t1
    await t2
```

Explanation:

`create_task` schedules each coroutine on the Event Loop so they overlap.

Follow-up Question:

How is this different from `await job("a")` then `await job("b")`?

## Level 4: await

Question:

Where does this coroutine release the Event Loop?

Think First:

Which line is the suspension point?

Starter Code:

```python
async def handler():
    data = await fetch()
    return process(data)
```

Expected Output:

At `await fetch()` the coroutine suspends and the loop runs other Tasks.

Explanation:

`await` releases the loop; `process(data)` runs after resume.

Follow-up Question:

Does `await` create a new thread?

## Level 5: gather()

Question:

Predict the result order.

Think First:

Does completion order change the results list?

Starter Code:

```python
async def slow():  await asyncio.sleep(2); return "slow"
async def fast():  await asyncio.sleep(1); return "fast"

a, b = await asyncio.gather(slow(), fast())
```

Expected Output:

```text
a = "slow"
b = "fast"
```

Explanation:

`gather` returns input order even though `fast` finished first.

Follow-up Question:

What is the total wait time, roughly?

## Level 6: Cancellation

Question:

Handle cancellation with cleanup.

Think First:

When is `CancelledError` raised?

Starter Code:

```python
async def job():
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        ...
```

Expected Output:

```python
    except asyncio.CancelledError:
        # cleanup here
        raise
```

Explanation:

`cancel()` injects `CancelledError` at the next await; cleanup runs, then re-raise.

Follow-up Question:

Why is cancellation not an immediate kill?

## Level 7: Exception Propagation

Question:

Where is the exception raised?

Think First:

When does a Task's stored exception surface?

Starter Code:

```python
async def boom():
    raise ValueError("x")

task = asyncio.create_task(boom())
await task
```

Expected Output:

`ValueError` is raised at `await task`.

Explanation:

The Task stores the exception; awaiting re-raises it to the caller.

Follow-up Question:

What warning appears if you never await `task`?

## Level 8: Semaphore

Question:

Limit OpenAI calls to 5 at a time.

Think First:

What guards the protected section?

Starter Code:

```python
sem = asyncio.Semaphore(5)

async def call(p):
    ...
```

Expected Output:

```python
async def call(p):
    async with sem:
        return await call_openai(p)
```

Explanation:

The semaphore admits at most 5 Tasks into the call section concurrently.

Follow-up Question:

What downstream failures does this prevent?

## Level 9: FastAPI Lifecycle

Question:

Explain the async endpoint lifecycle.

Think First:

Where does the request Task suspend?

Starter Code:

```python
@app.get("/user/{id}")
async def get_user(id: int):
    return await db.fetch_user(id)
```

Expected Output:

The request becomes a Task; at `await db.fetch_user(id)` it suspends and the loop serves other
requests, then resumes to return the response.

Explanation:

One worker serves many I/O-bound requests by overlapping their waits.

Follow-up Question:

What happens to the Task if the client disconnects?

---

# FastAPI Connections

FastAPI runs on an ASGI server with an Event Loop.

Request lifecycle:

```text
Request
   |
   v
ASGI server
   |
   v
Event Loop
   |
   v
Task (one per request)
   |
   v
await DB / OpenAI
   |
   v
Suspend  (loop serves other requests)
   |
   v
Resume
   |
   v
Response
```

## Async Endpoint

```python
@app.get("/chat")
async def chat(prompt: str):
    return await llm.complete(prompt)
```

At `await llm.complete(prompt)`, this request suspends and the worker serves other requests.

## Task Ownership and Cancellation

Each request is a Task owned by the loop. If the client disconnects, FastAPI can cancel the
request Task, which raises `CancelledError` at the current await so cleanup runs.

## Blocking Work: `asyncio.to_thread()`

```python
@app.get("/report")
async def report():
    # heavy, blocking, CPU or blocking-IO library
    data = await asyncio.to_thread(build_report)
    return data
```

`to_thread()` pushes blocking work to a thread so the Event Loop is not frozen.

What to watch for:

```text
Never call time.sleep or a blocking DB driver directly in async def.
Use async drivers, or to_thread() for unavoidable blocking calls.
```

---

# Playwright Connections

Playwright's async API awaits browser operations.

```python
await page.goto("https://example.com")
await page.click("#login")
await page.locator("#result").wait_for()
```

Each `await` suspends the current Task while the browser works, so the loop can drive other
jobs.

## Concurrent Browsers with a Semaphore

```python
sem = asyncio.Semaphore(5)

async def scrape(url):
    async with sem:
        context = await browser.new_context()
        try:
            page = await context.new_page()
            await page.goto(url)
            return await page.content()
        finally:
            await context.close()
```

Why the semaphore:

```text
Each BrowserContext costs memory.
Unlimited concurrent contexts -> browser explosion -> OOM.
Bounded concurrency -> stable scraping throughput.
```

Cleanup (Day12) still applies: close each `BrowserContext` in `finally`, even under
cancellation.

---

# AI Backend Connections

AI backends are almost entirely I/O-bound: OpenAI, Redis, PostgreSQL, MCP tools, weather APIs,
embedding APIs.

## Concurrent Tool Calls

```python
weather, embedding = await asyncio.gather(
    weather_api(city),
    embedding_api(text),
)
```

Independent I/O calls overlap instead of running one after another.

## Bounded Concurrency for Rate Limits

```python
sem = asyncio.Semaphore(10)

async def embed(text):
    async with sem:
        return await embedding_api(text)

vectors = await asyncio.gather(*[embed(t) for t in texts])
```

Why bound it:

```text
OpenAI returns HTTP 429 when you exceed the rate limit.
Redis and PostgreSQL have connection limits.
Bounded concurrency -> stable throughput, fewer retries, lower cost.
```

## Fire-and-forget Danger

```python
asyncio.create_task(log_usage())   # if this fails, error is lost
```

For important work, await the Task or attach a done callback so exceptions are not swallowed.

Production rule:

```text
Concurrency for independent I/O.
Semaphore for downstream capacity.
Await Tasks so failures are visible.
```

---

# English Interview

## Key Vocabulary

* event loop
* coroutine
* task
* `await`
* suspend / resume
* cooperative scheduling
* blocking vs non-blocking
* concurrency vs parallelism
* `asyncio.gather()`
* cancellation
* `CancelledError`
* semaphore
* throughput
* rate limit

## Example Answer

Async programming lets a single-threaded Event Loop serve many I/O-bound Tasks by suspending a
coroutine at each `await` and running other Tasks while it waits. It improves throughput for
I/O work, but not CPU-bound work, because only one line of Python runs at a time.

## Beginner Questions

Question:

What is async?

Standard Answer:

Async is a concurrency model where an Event Loop runs many I/O-bound Tasks on one thread by
suspending each Task at `await` and resuming it when its I/O is ready.

Question:

What is `await`?

Standard Answer:

`await` suspends the current coroutine and releases the Event Loop so other Tasks can run. It
does not create a thread.

Question:

What is a coroutine?

Standard Answer:

A coroutine is a pausable, resumable unit of work defined with `async def`. Calling it creates
a coroutine object, which is an execution plan the Event Loop runs.

## Intermediate Questions

Question:

Explain the Event Loop.

中文解析:

事件循环是单线程的协作式调度器。它在 await 处暂停当前 Task，运行就绪队列里的其他 Task，I/O 就绪后再恢复。

Standard Answer:

The Event Loop is a single-threaded cooperative scheduler. It runs a Task until it hits an
`await`, suspends it, runs other ready Tasks, and resumes it when its awaited I/O completes.

Follow-up Question:

How can one thread give concurrency?

Production Discussion:

One worker serving many awaiting requests is why async backends scale for I/O.

Question:

Task vs Coroutine?

中文解析:

协程是执行计划；Task 是事件循环正在驱动的协程，创建后立即并发运行。

Standard Answer:

A coroutine is an execution plan. A Task is a coroutine scheduled on the Event Loop that runs
concurrently. `create_task` starts it now; `await coro()` runs it inline.

Follow-up Question:

When do you need a Task instead of a bare `await`?

Question:

What does `gather()` do?

中文解析:

gather 并发运行多个协程，并按输入顺序返回结果，与完成顺序无关。

Standard Answer:

`gather()` runs multiple coroutines concurrently and returns their results in input order,
regardless of completion order.

Follow-up Question:

Why is input order important for unpacking results?

Question:

Explain cancellation.

中文解析:

cancel() 是协作式的，只在下一个 await 处抛出 CancelledError，需要在 except/finally 里清理并通常重新抛出。

Standard Answer:

Cancellation is cooperative. `task.cancel()` requests cancellation, and `CancelledError` is
raised at the next await, so cleanup runs before the Task ends.

Follow-up Question:

Why is it not an immediate kill?

## Senior Questions

Question:

How does async improve backend throughput?

Standard Answer:

Backend latency is mostly I/O. Async overlaps that waiting, so one worker serves many
concurrent requests instead of blocking on each one. It raises throughput for I/O, not CPU.

Interview Review:

Strong answers separate throughput from speed and mention the single thread.

Production Case:

A FastAPI worker awaiting OpenAI serves other requests during the wait instead of blocking.

Question:

Explain Event Loop scheduling.

Standard Answer:

The loop keeps a ready queue and a waiting set. It runs a Task until `await`, moves it to
waiting, runs the next ready Task, and resumes waiters when their I/O completes. It is
cooperative and single-threaded.

Interview Review:

Good answers note that a blocking call freezes all scheduling.

Production Case:

A stray `time.sleep` in async code freezes every concurrent request on that worker.

Question:

Why use a Semaphore?

Standard Answer:

A semaphore bounds concurrency so downstream systems are not overloaded. Unlimited `gather()`
can trigger rate limits, timeouts, and connection-pool exhaustion.

Interview Review:

Senior answers optimize for stable throughput, not maximum concurrency.

Production Case:

Limiting concurrent OpenAI calls to 10 avoids HTTP 429 and keeps latency predictable.

Question:

How do you control production concurrency?

Standard Answer:

Use bounded `gather()` with a semaphore, respect connection-pool sizes, keep blocking work in
`to_thread()`, and await Tasks so failures surface. Target stable throughput.

Interview Review:

Look for downstream capacity awareness: OpenAI, Redis, PostgreSQL, GPU, browser.

Production Case:

Embedding 100k texts is chunked behind a semaphore to respect rate limits and pool sizes.

Question:

Explain FastAPI async architecture.

Standard Answer:

An ASGI server runs an Event Loop; each request is a Task. At each `await` on the DB or an API
the request suspends and the worker serves others. Client disconnects can cancel the request
Task.

Interview Review:

Strong answers mention `to_thread()` for blocking work and cancellation on disconnect.

Production Case:

An async endpoint awaiting PostgreSQL scales because the worker is not blocked during queries.

Question:

How do you handle AI backend concurrency?

Standard Answer:

Run independent I/O with `gather()`, bound external calls with a semaphore, handle 429 with
backoff, and await Tasks so exceptions are visible. Optimize for stable throughput.

Interview Review:

This connects async to real agent and RAG pipelines.

Production Case:

A RAG request concurrently fetches context from Redis and PostgreSQL, then calls the LLM under
a semaphore.

---

# Today's Takeaway

Async is about the Event Loop overlapping waiting, not about parallel CPU work.

```text
Ask always:
What is the Event Loop doing?
Which Task is running?
Which Task is suspended?
Why is the scheduler switching?
```

Today's core principles:

* Async improves I/O throughput, not CPU speed.
* The Event Loop is a single-threaded cooperative scheduler.
* Blocking calls freeze the entire loop; use async APIs or `to_thread()`.
* A coroutine is a plan; a Task is a coroutine the loop is driving.
* `await` suspends the coroutine and releases the loop, without threads.
* `gather()` runs concurrently and returns input order.
* Cancellation is cooperative and raises `CancelledError` at the next await.
* A Task stores its exception until you await it.
* A `Semaphore` protects downstream capacity for stable throughput.
* FastAPI, Playwright, and AI backends are I/O-bound and rely on this model.

The most important engineering sentence:

```text
Concurrency is overlapping waiting; optimize for stable throughput, not maximum concurrency.
```

---

# Before Next Lesson Checklist

Before Day14, confirm you can answer these without looking at the notes:

- [ ] Why does async help I/O but not CPU work?
- [ ] What is the difference between blocking and non-blocking?
- [ ] Why does one blocking call freeze the whole Event Loop?
- [ ] What is the Event Loop doing during an `await`?
- [ ] Why does calling a coroutine function not run its code?
- [ ] What is the difference between a coroutine and a Task?
- [ ] What three things does `await` do?
- [ ] Why does `gather()` return input order, not completion order?
- [ ] What are the Task lifecycle states?
- [ ] Why is cancellation cooperative and not an immediate kill?
- [ ] When is a Task's exception raised?
- [ ] Why can unlimited `gather()` be dangerous?
- [ ] How does a `Semaphore` create stable throughput?
- [ ] How does a FastAPI request move through the Event Loop?
- [ ] Can I explain async throughput in an interview in English?
