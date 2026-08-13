# Day62 — Playwright Runtime, Locators and Reliable Async Interaction

## 1. Lesson Metadata

```text
Status:        ✅ Completed — EXECUTED_LOCAL_RUNTIME (controlled HTTP page + pure-logic + classroom Chromium)
Version:       v2 (LESSON_TEMPLATE_v2, 16 sections)
Difficulty:    Intermediate–Advanced
Estimated Time: 4 hours
Prerequisite:  Day61 real backend integration (FastAPI → Outbox → Celery → Worker → Provider → Object Storage → OTel)
Previous Lesson: Day61 — Object Storage, Provider Adapter and OpenTelemetry End-to-End Evidence
Next Lesson:   Day63 — Tenant-authenticated BrowserContext isolation
Engineering Artifact: projects/fastapi-playwright/ (controlled research page + interaction logic + async browser task + tests)
```

Day62 turns the browser into a *reliable* capability. Day61 proved that only durable/observable
facts — not transport or HTTP impressions — decide what may be claimed. Day62 carries that rule
into the browser: a fixed sleep or a brittle CSS selector is a guess; a Locator waiting on an
observable business condition is evidence.

> Evidence honesty: the runnable artifact's pure interaction/cleanup logic + the controlled
> research page over REAL HTTP loopback + the static reliability-contract checks all run and pass —
> **13 passed, 1 skipped, `EXECUTED_LOCAL_RUNTIME`**, run with:
>
> ```
> cd projects/fastapi-playwright
> python3 -m pytest -q tests/
> ```
>
> The 1 skipped test is the real-Chromium suite, gated on the `playwright` package (absent in the
> updating agent's environment). In class, a real Chromium opened
> `/research?overlay_delay_ms=800`, a semantic snapshot found the Company textbox, Search button
> and results status, and filling `Acme` + clicking the `data-testid` button produced the dynamic
> `Results for Acme` — an `EXECUTED_LOCAL_RUNTIME` browser-interaction fact, never integration or
> production. **NOT RUN by the updating agent:** the Python async `finally` cleanup and the
> blocked-overlay action-timeout negative case against a live browser (covered by the pure-logic
> contract + the gated real-Chromium tests), plus everything Day63+ (auth/session isolation,
> network/artifact flow, recovery/security policy, queue integration, and production).

---

## 2. Learning Objectives

After completing this lesson, the student should be able to:

* Explain the Browser / BrowserContext / Page ownership model and why each task owns its own
  Context as a state and fault-isolation boundary.
* Distinguish a Locator (a re-resolvable target contract) from a cached DOM node, and choose
  role + accessible name or a maintained `data-testid` over dynamic CSS or positional `nth()`.
* Compare actionability waiting (`Locator.click()` waits until an action can be performed) with a
  business assertion (wait until a business fact is true), and explain why actionability is not
  business completion.
* Classify a timeout, a login redirect and a Page crash as UNKNOWN or a FAILED precondition —
  never business `no result` and never permission for a blind retry.
* Implement an async task that creates one Context per task, waits on observable conditions,
  never uses fixed sleep or `force=True`, closes the Context in `finally`, and preserves the
  primary operation error when cleanup also fails.
* Diagnose a production `data-testid` rename that causes Browser Worker timeouts and defend the
  rollback (contract restore + re-verify) over a forced click or brittle CSS fallback.
* Answer, in English, why a Locator is a contract and why an unknown outcome must not be reported
  as a business result.

---

## 3. Why This Matters

Browser automation is where "it worked on my machine" quietly becomes a production incident. A
fixed `sleep(2)` passes on a fast laptop and flakes on a loaded CI runner; a CSS selector tied to
a build-hashed class breaks the next frontend release. When an AI Research Browser Worker drives a
real page, three failures dominate:

- **Flakiness at scale** — timing guesses race against real network and render latency, so the
  same task passes and fails nondescriptly. Reliability, not raw speed, is the metric.
- **Silent wrong claims** — a click that "succeeded" (actionability) is reported as a completed
  business task even though no result was ever rendered. This is the Day61 mistake in a new
  costume: an HTTP/interaction impression is not business truth.
- **State leakage and blast radius** — reusing one live Context across tasks leaks cookies, form
  state and auth, and lets one task's failure poison another. A per-task Context bounds the blast
  radius.

The cost is concrete: retried browser jobs burn compute, a mis-reported "no result" corrupts
downstream data, and a forced click hides a real regression until it reaches customers. Day62
builds the primitives that make the browser a *dependable* tool the later lessons can secure
(Day63), extract from (Day64), recover (Day65) and queue (Day66).

---

## 4. Roadmap Position

```text
Day61 backend execution + evidence (FastAPI → Outbox → Celery → Worker → Provider → Storage → OTel)
        |
        v
Day62 reliable browser-runtime primitives (ownership, Locators, waiting, cleanup)   <-- you are here
        |
        v
Day63 tenant-authenticated BrowserContext isolation
        |
        v
Day64 dynamic extraction + Object Storage artifacts
        |
        v
Day65 browser failure / security boundaries
        |
        v
Day66 queue-backed permissioned browser Worker
```

Day62 is the first Playwright lesson of Phase 5's browser arc. It appears here because the backend
that will *drive* the browser is already real (Day59–61): a durable Job lifecycle, a Worker with
lease-fenced authority, and an evidence discipline. Day62 supplies the browser-side counterpart of
that discipline so Day63 can create tenant-bound Contexts from controlled storage state, Day64 can
persist approved artifacts through the Day61 Object Storage boundary, and Day66 can bind the
capability to the durable Job.

### Knowledge Continuity

```text
Previous Knowledge
  - Day61 rule: timeout ≠ non-execution; durable/observable facts decide claims
  - Day60 Worker/lease ownership + one authoritative attempt at a time
  - Day47 async unit-of-work discipline
        |
        v
Current Lesson Concept
  - Browser reuse + per-task Context/Page ownership
  - Locator contract + auto-waiting vs business assertion
  - honest timeout/cleanup boundaries
        |
        v
Future Production Usage
  - Day63 tenant-bound Contexts from controlled storage state
  - Day64 structured extraction + artifact persistence
  - Day65 recovery/security policy; Day66 queue-backed browser Worker
```

Reused mental models (named): the **Day61 evidence rule** (observable facts, not impressions),
the **Day60 ownership/authority model** (one owner acts; failure is bounded), and the **Day47
`finally` unit-of-work** discipline (cleanup is part of the operation, not an afterthought).

---

## 5. Lesson Map

```text
Browser (reused)
  -> BrowserContext (one per task, owns state + isolation)
    -> Page (the task's surface)
      -> Locator (re-resolvable contract: role/name or data-testid)
        -> auto-waiting (actionability)
          -> business assertion (a business fact is true)
            -> timeout / login / crash = unknown or failed precondition
              -> finally: close Context (preserve primary error)
```

---

## 6. Core Mental Model

```text
Browser        = process-level reusable runtime
BrowserContext = per-task state and fault-isolation boundary
Page           = a task's concrete browsing surface

Locator        = repeatable target contract (role/name or maintained test-id)
auto-waiting    = wait until an action CAN be performed (actionability)
assertion       = wait until a business FACT is true

timeout / login redirect / Page crash = UNKNOWN outcome or FAILED precondition
task success = business result asserted  AND  Context cleanup completed
```

The single sentence to remember: **actionability is not business completion, and cleanup is part
of the task.** A click can be actionable while the business result never renders; a business
assertion can pass while `context.close()` fails. Only "business asserted AND cleanup completed"
is success.

---
## 7. Main Concepts

### Concept 1: From time-waiting to observable business conditions

#### Tech Lead Question

The unsafe first version did `sleep(2)` then read a CSS selector. What is the progression from
"waiting on time" to "waiting on the right thing"?

#### Student Thinking

The student reasoned that a sleep is just a guess about how long rendering takes, and that what we
actually care about is whether specific things are on the page — first that the interactive
element is there, then that a result element appears, then that the result text is what we asked
for.

#### Student Answer

> The progression is element appearance, then result-element appearance, then result-text update.

#### Tech Lead Review

Correct, and precisely staged. A fixed sleep guesses time; it does not prove an element is present
or actionable. The three observable conditions map to real facts: (1) the interactive control
exists and is ready, (2) a result region appears, (3) the result *text* becomes the business
answer. Playwright's auto-waiting handles (1) as actionability; (2) and (3) are business
assertions you must add — auto-waiting alone will happily click and move on while the page renders
nothing.

#### Engineering Thinking

- Why it exists: real render/network latency is variable; time-based waits trade reliability for a
  magic number that is simultaneously too long (slow) and too short (flaky).
- Alternatives: `networkidle` feels like "the page is done", but it is not universal business
  readiness — a page can be network-idle with no result rendered, or busy with the result already
  present. Assert the business condition, not the transport state.
- Production risk controlled: nondeterministic flakiness and false "done" claims.

#### Production Example

An AI Research Worker fills a company name and clicks Search. With `sleep(2)` it sometimes reads an
empty results node (render not finished) and reports "no result"; with an assertion on
`Results for <query>` it either observes the fact or times out honestly.

#### Framework Connection

Playwright `expect(locator).to_have_text(...)` retries until the condition holds or the timeout
elapses — a business assertion, distinct from `Locator.click()`'s actionability wait.

---

### Concept 2: Locator is a contract, not a cached node

#### Tech Lead Question

Is a Locator a DOM node you saved? What makes one Locator stable and another brittle?

#### Student Thinking

The student initially framed it as "the Locator is a stable contract, whereas CSS is a method for
element positioning" — close, but conflating the *stability source* with the *mechanism*.

#### Student Answer

> The Playwright locator represents a stable contract, whereas CSS is a method for element
> positioning.

#### Tech Lead Review

The instinct is right but needs sharpening. A Locator is a *re-resolvable target query* — it
re-finds the element each time it acts, so it is not a cached node that goes stale. But stability
does not come from "being a Locator"; it comes from *what the Locator matches*: a maintained
role/accessible-name or a stable `data-testid` contract. CSS is itself a locator mechanism; it is
brittle when it depends on implementation details (build-hashed classes, positional `nth()`).
Prefer role + accessible name, scope within a business region, and use a `data-testid` contract
when semantics are insufficient.

#### Engineering Thinking

- Why it exists: UIs change markup constantly; a target tied to *meaning* (role/name) or an
  explicit *contract* (test-id) survives refactors that a CSS path or index does not.
- Alternatives: dynamic CSS classes and `nth()` as defaults — avoid; they track implementation.
- Production risk controlled: mass selector breakage on frontend releases.

#### Production Example

`page.get_by_role("button", name="Search")` or `get_by_test_id("company-search-submit")` scoped
inside the research form survives a CSS refactor; `.btn.btn-primary.css-1x2y3z` does not.

#### Framework Connection

Playwright `get_by_role`, `get_by_label`, `get_by_test_id`, and region scoping
(`form.get_by_role(...)`) encode the contract; `nth()` is a last resort, not a default.

---

### Concept 3: Browser / Context / Page ownership

#### Tech Lead Question

The Browser may be reused across tasks. Where does per-task state live, and what does each task
own?

#### Student Thinking

The student saw that launching a Browser per task is wasteful, but that sharing state across tasks
is dangerous, so the boundary must be below the Browser.

#### Student Answer

> Reuse the Browser, but create a new Context and a new Page per task.

#### Tech Lead Review

Exactly the model. The Browser is a process-level reusable runtime. Every task creates and OWNS
its own BrowserContext — the per-task state and fault-isolation boundary — and the Context owns its
Page(s). Task success or failure closes its Context in `finally`; the Browser closes only on Worker
drain/stop or a Browser-level failure. A Page failure need not technically destroy the Context, but
for Day62's one-task-one-Context model you discard that Context because the task state is no longer
trustworthy. Crucially, a Browser failure invalidates every Context and Page, while Task A's
failure must never close an independent Context B.

#### Engineering Thinking

- Why it exists: Contexts are cheap, isolated "incognito profiles"; they bound cookies, storage and
  auth per task and contain the blast radius of a failure.
- Alternatives: one shared live Context (leaks state, couples failures) or a Browser per task
  (wasteful). The reuse-Browser + per-task-Context split is the balanced default.
- Production risk controlled: cross-task state leakage and failure coupling.

#### Production Example

Two research tasks run on one reused Browser. Task A hits a crash; closing A's Context leaves B
untouched. Day63 will create each Context from controlled tenant-bound storage state rather than
sharing one live Context.

#### Framework Connection

`browser.new_context()` per task, `context.new_page()`, `context.close()` in `finally`. A
Context-closed `new_page()` is an error — the surface is gone.

---

### Concept 4: Actionability wait vs business assertion, and honest timeouts

#### Tech Lead Question

`Locator.click()` already waits. So if the click "succeeds", is the task done? And if it times out,
is that "no result"?

#### Student Thinking

The student separated "the button could be clicked" from "the business result appeared", and
recognized that a timeout tells you nothing about the business outcome.

#### Student Answer

> `click()` waits for actionability, but a business assertion waits for a business fact.
> Actionability is not business completion. A timeout is unknown, a login page is a session/auth
> precondition failure, a Browser failure is wider than a Page failure, and a Context-closed
> `new_page()` is an error.

#### Tech Lead Review

All correct. Actionability means the element is visible, enabled, stable and hittable — nothing
about whether the result rendered. So after the click you assert the business fact
(`Results for <query>`). And an interaction failure is not a business answer: a timeout, a login
redirect and a Page crash mean UNKNOWN outcome or a FAILED precondition — never business `no
result` and never a license to blind-retry (a duplicate action could double a side effect;
recovery policy is Day65). This is the Day61 rule ported to the browser: an impression is not
truth.

#### Engineering Thinking

- Why it exists: conflating actionability with completion produces confident wrong claims; treating
  "unknown" as "no result" corrupts downstream data.
- Alternatives: `force=True` to push through — forbidden here; it hides the real actionability
  failure. Wait for an observable condition (overlay hidden, `data-state=ready`) instead.
- Production risk controlled: fabricated results and unsafe retries.

#### Production Example

An overlay lingers past the action budget; the honest outcome is a bounded timeout (FAILED /
unknown), preserved for reconciliation — not a forced click and not a fake "no result".

#### Framework Connection

`expect(overlay).to_have_attribute("data-state", "ready")` then `expect(results).to_have_text(...)`;
`to_be_hidden()` accepts both absent and hidden overlays (both are "not currently blocking").

---

### Concept 5: Cleanup is part of the task; preserve the primary error

#### Tech Lead Question

The business assertion passed, but `context.close()` throws. Is the task fully successful? And if
both the operation and cleanup fail, which error do you report?

#### Student Thinking

The student reasoned that leaving a Context open means resources and state are not actually
reclaimed, so the task cannot be called fully done; and that when both fail, the original cause is
the useful signal.

#### Student Answer

> If the assertion passed but cleanup failed, the task is incomplete, not fully successful. When
> the operation error and the cleanup error both occur, the original operation error is primary.

#### Tech Lead Review

Correct and important. Report "business asserted AND cleanup completed" as success; a passed
assertion with a failed `context.close()` is INCOMPLETE — resources/state were not reclaimed and a
later task could be affected. When operation and cleanup both fail, preserve the ORIGINAL operation
error as the reported cause and attach the cleanup failure as additional diagnostics; a `finally`
that swallows the primary error and re-raises the cleanup error destroys the most useful signal.

#### Engineering Thinking

- Why it exists: cleanup failures are real (a crashed Page can make `close()` throw), and the
  original failure is what an operator must act on.
- Alternatives: a bare `finally: context.close()` without try/except lets a cleanup error mask the
  real cause — an anti-pattern.
- Production risk controlled: misleading incident triage and leaked Contexts.

#### Production Example

`classify_task_result(operation_error, cleanup_error)` returns `FAILED` with the operation error
primary and the cleanup failure in diagnostics; a clean run with a failed close returns
`INCOMPLETE`, not `SUCCESS`.

#### Framework Connection

Python `try/except/finally` with a nested try around `context.close()`; mirrors the Day47
unit-of-work cleanup discipline.

---

### Concept 6: The page owns its behavior — never mutate the DOM to fake success

#### Tech Lead Question

Why serve a real local HTTP page instead of a `file://` page, and why must Playwright not set the
result text itself?

#### Student Thinking

The student initially thought `file://` is fine because it "opens HTML", and had to see that a
faithful test models routing and controlled delay.

#### Student Answer

> Use a local HTTP page (not `file://`), a form-scoped Locator, a stable `data-testid`, no
> `force=True`, a parameterized `overlay_delay_ms`, and a timeout when the delay exceeds the
> action budget.

#### Tech Lead Review

Right on all counts. `file://` can open HTML, but local HTTP models route/query/request/response
behavior faithfully and supports controlled delay injection (`?overlay_delay_ms=N`). And Playwright
must never directly mutate the DOM to manufacture success: the test page's OWN JavaScript removes
its overlay, handles the click, and asynchronously renders the result. If the automation set the
text itself, the test would prove nothing about the page. Same-tenant tasks must also not share one
live Context — Day63 creates a new Context per task from controlled tenant-bound storage state; a
shared live Context leaks state and weakens fault isolation.

#### Engineering Thinking

- Why it exists: a test is only evidence if the *page* produces the outcome; a controlled server
  lets you inject realistic delay without external flakiness.
- Alternatives: `file://` (no routing/delay control) or DOM injection (fakes the result) — both
  destroy the test's meaning.
- Production risk controlled: green tests that prove nothing; hidden regressions.

#### Production Example

`day62_research_page.py` serves the page; its own script clears the overlay after
`overlay_delay_ms`, handles the Search click, and renders `Results for <query>`. The HTTP-loopback
test asserts the server never ships a pre-rendered result string.

#### Framework Connection

`http.server` for the controlled page; Playwright drives only user-equivalent events
(`fill`, `click`) and asserts the page's own output.

---
## 8. Common Misconceptions

**Fixed sleep proves readiness**

❌ `sleep(2)` means the element is ready.
✅ A sleep guesses time; it proves nothing. Wait on an observable condition (element ready /
`data-state=ready`) and assert the business fact.

Why beginners think this: it "usually works" locally.
How to remember: time is not a fact; a rendered condition is.

**A Locator is a saved DOM node**

❌ A Locator caches the element it found.
✅ A Locator is a re-resolvable query; it re-finds the element each action. Stability comes from a
maintained role/name or `data-testid` contract, not from CSS/`nth()`.

Why beginners think this: other frameworks return handles that go stale.
How to remember: Locator = contract, resolved on use.

**Actionability means the task is done**

❌ The click succeeded, so the task completed.
✅ Actionability ≠ business completion. Assert the business result after the action.

Why beginners think this: `click()` "waited", so it feels complete.
How to remember: could-click ≠ did-the-work.

**A timeout means "no result"**

❌ It timed out, so there is nothing to find.
✅ Timeout / login redirect / Page crash = UNKNOWN or FAILED precondition — never business `no
result`, never blind-retry permission.

Why beginners think this: absence of a result looks like "no result".
How to remember: unknown is not empty (Day61 rule in the browser).

**`file://` is good enough, and Playwright can set the text**

❌ Open the HTML file directly and, if needed, set the result via the automation.
✅ Use local HTTP (routing + controlled delay); the page's OWN JS must render the result. DOM
mutation by the automation fakes success and proves nothing.

Why beginners think this: it makes the test go green fast.
How to remember: the page must do the work, or the test is theater.

**`force=True` fixes a blocked click**

❌ Use `force=True` to click through an overlay.
✅ Never hide an actionability failure; wait for the overlay hidden / `data-state=ready`.
`to_be_hidden()` accepts absent and hidden overlays.

Why beginners think this: it removes the error.
How to remember: force hides the bug you needed to see.

---

## 9. Engineering Trade-offs

**Role/accessible-name Locator vs `data-testid` contract vs CSS/`nth()`**

Role + name:
- Ties to meaning and accessibility; survives markup churn.
- May be ambiguous when several controls share a name (scope within a region).

`data-testid`:
- An explicit, maintained contract; unambiguous and stable.
- Requires frontend cooperation; a rename (see the rollback exercise) breaks Workers.

Dynamic CSS / `nth()`:
- Quick to write.
- Tracks implementation details/order; brittle across releases. Avoid as a default.

Tech Lead review: prefer role/name, scope to a business region, add a `data-testid` when semantics
are insufficient, and treat the test-id as a versioned contract between frontend and automation.

**Reuse one Browser + per-task Context vs Browser-per-task vs one shared Context**

Reuse Browser + per-task Context (chosen):
- Cheap isolation, bounded blast radius, fast.
- Requires disciplined `finally` cleanup.

Browser-per-task:
- Maximum isolation.
- Wasteful (process launch cost) and slow at volume.

One shared live Context:
- Cheapest.
- Leaks cookies/auth/state and couples failures — rejected.

Tech Lead review: default to reuse-Browser + per-task-Context; escalate to Browser-per-task only
for hard isolation needs.

**Honest timeout (bounded failure) vs `force=True` / blind retry**

Honest timeout:
- Preserves truth (unknown), enables safe reconciliation later.
- Fails the task now (costs a retry decision to a policy).

`force=True` / blind retry:
- Appears to "recover".
- Hides regressions and risks duplicate side effects — rejected here; recovery is Day65.

---

## 10. Hands-on Exercises

### Exercise 1: Stage the waits

Question: Rewrite `sleep(2); read(css)` into three observable stages.

Think First: which facts, in what order?

Starter Artifact: `src/day62_browser_task.py` (the ready → fill → click → assert flow).

Expected Output: wait overlay `data-state=ready` → fill Company → click Search → assert
`Results for <query>`.

Explanation: actionability then business assertion; no fixed sleep.

Follow-up Question: why is `networkidle` not a substitute for the final assertion?

### Exercise 2: Classify the outcome (design judgment)

Question: For signals `timeout`, `login_redirect`, `page_crash`, `empty_results_rendered`, give the
outcome class and whether a blind retry is allowed.

Think First: which are unknown, which is a precondition, which is a real business fact?

Starter Artifact: `src/day62_interaction_logic.py::classify_interaction_signal` + `may_blind_retry`.

Expected Output: unknown / precondition_failed / unknown / business_no_result; blind retry always
false.

Explanation: unknown ≠ no result; recovery is a Day65 policy.

Follow-up Question: why is an ASSERTED empty result different from a timeout?

### Exercise 3: Cleanup honesty (reusable artifact)

Question: Implement the task-outcome combination for (op ok, cleanup fail) and (op fail, cleanup
fail).

Think First: which error is primary; what is the status?

Starter Artifact: `src/day62_interaction_logic.py::classify_task_result`.

Expected Output: `INCOMPLETE` for the first; `FAILED` with the operation error primary and cleanup
in diagnostics for the second.

Explanation: cleanup is part of the task; never let cleanup mask the primary error.

Follow-up Question: what would a bare `finally: context.close()` do to incident triage?

### Exercise 4: Contract rollback drill (production judgment)

Question: A frontend release renames `data-testid="company-search-submit"` to `search-submit`;
Workers time out. What do you do?

Think First: is this a locator bug or a contract break?

Expected Output: pause affected new work, correlate with the frontend release, roll back the
frontend test-id contract, re-verify locally/pre-release, retain timed-out tasks as unknown; do NOT
switch to `force=True`, brittle CSS, or blind retries (retry policy is Day65).

Explanation: a test-id is a contract; restore it rather than route around it.

Follow-up Question: what evidence do you preserve for the timed-out tasks, and why?

---

## 11. Relevant Framework Connections

**Playwright** (primary): `browser.new_context()` / `context.new_page()` / `context.close()` for
ownership; `get_by_role`, `get_by_label`, `get_by_test_id`, region scoping for the Locator
contract; `Locator.click()` actionability vs `expect(locator).to_have_text(...)` /
`to_have_attribute(...)` / `to_be_hidden()` for business assertions. What to share: the Browser.
What to isolate: the Context per task. Failure: a Browser failure invalidates all Contexts; a
Context-closed `new_page()` errors. Review: no fixed sleep, no `force=True`, `finally` cleanup that
preserves the primary error.

**FastAPI / Celery Worker** (from Day59–61): the browser task will run inside a Worker that already
owns a durable Job with lease-fenced authority. The same evidence rule applies — the Worker may
claim only what an observable browser fact supports. Day66 binds this to the Job lifecycle.

**Local HTTP (`http.server`)**: the controlled research page models route/query/request/response
and injects a bounded `overlay_delay_ms`, exactly the controllable surface a reliable-interaction
test needs. This is a genuine connection, not decoration — the delay parameter is what makes the
actionability/timeout behavior testable.

Future connections (labeled, not implemented here): Object Storage (Day64 artifact persistence),
auth/session storage state (Day63), and Redis/Celery queue integration (Day66).

---
## 12. AI Backend Connections

The browser is a *tool* in an AI Backend, and Day62 makes it a dependable one:

- **Agent tool calling**: an "AI Research Browser" is a tool an agent invokes. If the tool reports
  actionability as completion, the agent ingests fabricated results and compounds the error
  downstream. A business assertion (`Results for <query>`) is the tool's contract for "the fact is
  true", mirroring Day61's "verified result, not an impression".
- **Queue-backed browser Workers**: at scale the browser runs behind a Celery Worker (Day66). One
  reused Browser with a per-task Context bounds cost and blast radius; a shared live Context would
  leak one tenant's session into another's task — a data-privacy incident, not just a bug.
- **Cost control**: fixed sleeps and blind retries burn GPU/CPU and wall-clock; observable-condition
  waits and honest timeouts cap the spend and make retries a deliberate policy decision.
- **Data privacy / isolation**: per-task Contexts are the browser-side analogue of tenant isolation.
  Day63 creates each Context from controlled tenant-bound storage state so login state never leaks
  across tasks — and login state, cookies and tokens are never committed.
- **Observability**: the Day61 evidence discipline extends here — a timed-out browser task is
  UNKNOWN and is preserved for reconciliation, not silently dropped or reported as "no result".

Production implication: a browser tool that cannot distinguish "unknown" from "no result", or
"actionable" from "done", will silently poison an agent's downstream reasoning and any data it
persists. Reliability is a correctness property, not a nicety.

---

## 13. English Interview

### Key Vocabulary

```text
Browser / BrowserContext / Page · Locator · actionability · auto-waiting
business assertion · data-testid contract · role + accessible name
unknown outcome · failed precondition · blind retry · Context cleanup in finally
overlay / data-state=ready · force=True (avoid) · networkidle (not business readiness)
```

### Useful Expressions

- "A Locator is a re-resolvable contract, not a cached node."
- "Actionability is not business completion."
- "A timeout is unknown, not a business no-result."
- "Cleanup is part of the task; a failed close means incomplete, not successful."

### Beginner Question

Q: What is the difference between a Playwright Locator and a CSS selector?

Weak Answer: "The Locator is a stable contract, whereas CSS is a method for element positioning."

Strong Answer: "A Locator is a re-resolvable target query — it re-finds the element each time it
acts, so it does not go stale. Its stability comes from what it matches: a maintained role/
accessible-name or a stable `data-testid` contract. CSS is itself a locator mechanism, and it is
brittle when it depends on implementation details like build-hashed classes or positional `nth()`.
So I prefer role + name, scope to a business region, and use a `data-testid` when semantics aren't
enough."

### Intermediate Question

Q: A browser task times out. What do you do, and why not retry?

Weak Answer: "Since the outcome is unknown, I preserve evidence for the verification process."

Strong Answer: "A timeout is an UNKNOWN outcome, not a business `no result`, so I don't report a
result and I don't blind-retry — a duplicate action could double a side effect. I preserve safe
diagnostics (what condition I was waiting for, the URL, timings — never secrets or full sensitive
payloads), keep the task as unknown, and defer any retry to an explicit recovery/reconciliation
policy that accounts for duplicate-side-effect risk. This is the Day61 rule: transport/interaction
impressions aren't business truth."

### Senior Question

Q: A frontend release renamed a `data-testid` and Browser Workers are timing out at scale. Walk me
through the response.

Strong Answer: "First contain: pause affected new work and preserve diagnostics — don't let the
fleet keep timing out. Then correlate the spike with the frontend release and confirm the renamed
test-id is the cause. The fix is to roll back the frontend test-id contract (or ship a coordinated
contract update), not to route around it with `force=True` or a brittle CSS fallback, which would
hide the regression and risk duplicate actions. Re-verify locally and pre-release against the
restored contract, and retain the timed-out tasks as unknown for the recovery policy to reconcile —
I don't reclassify them as `no result`. The test-id is a versioned contract between frontend and
automation; the durable fix is to honor it."

### Common Weak Answer

"The click worked and the page looked done, so the task succeeded." This confuses actionability
with business completion and skips the business assertion and Context cleanup.

### Strong Answer (summary)

"Task success = the business fact asserted AND the Context cleanup completed. Actionability,
`networkidle`, or a click that 'worked' are not business truth; a timeout is unknown; and a failed
`context.close()` after a passed assertion means incomplete, not successful."

---

## 14. Mental Model Summary

```text
Browser        = reusable process runtime
BrowserContext = per-task state + isolation boundary
Page           = task browsing surface
Locator        = re-resolvable contract (role/name or maintained test-id)
auto-waiting    = actionability (can act)
assertion       = business fact is true (did the work)
timeout/login/crash = unknown / failed precondition (never "no result", never blind retry)
task success   = business asserted  AND  context.close() completed
force=True      = forbidden (hides actionability failure)
DOM mutation    = forbidden (fakes the page's own result)
```

---

## 15. Today's Takeaway

- **Most important mental model**: task success = business result asserted AND Context cleanup
  completed; actionability is not completion.
- **Most important production risk**: reporting an interaction impression (click worked / timeout)
  as business truth — the Day61 mistake in the browser.
- **Most important trade-off**: role/name + `data-testid` contract over brittle CSS/`nth()`;
  reuse-Browser + per-task-Context over shared or per-task Browser.
- **Most important framework connection**: Playwright Locators + `expect(...)` business assertions
  vs `Locator.click()` actionability; `finally` Context cleanup that preserves the primary error.
- **Most important AI Backend connection**: a browser tool that can't tell "unknown" from "no
  result" poisons an agent's downstream reasoning.
- **Most important interview answer**: "A Locator is a re-resolvable contract; a timeout is unknown,
  not empty; cleanup is part of the task."

---

## 16. Before Next Lesson Checklist

- [ ] I can explain Browser / BrowserContext / Page ownership and why each task owns its Context.
- [ ] I can state WHY a Locator is a contract, not a cached node, and choose role/name or test-id.
- [ ] I can name the production risk: actionability/timeout reported as business truth.
- [ ] I can correct the misconception that a timeout means "no result".
- [ ] I can defend the trade-off: `data-testid` contract vs brittle CSS; reuse-Browser + per-task
      Context.
- [ ] I can run the artifact: `python3 -m pytest -q tests/` (= 13 passed, 1 skipped; pure-logic +
      HTTP-loopback + static reliability-contract checks all run; only the real-Chromium suite is
      gated on `playwright`).
- [ ] I can connect this to Playwright (Locators, actionability vs assertion, cleanup).
- [ ] I can connect it to AI Backend (agent tool calling, per-task Context isolation, cost).
- [ ] I can answer in English why a timeout is unknown and why cleanup failure means incomplete.

---

Related: [Day62 design/runbook](../../projects/fastapi-playwright/docs/day62-playwright-runtime-locators-and-reliable-async-interaction-design.md) ·
[interaction logic](../../projects/fastapi-playwright/src/day62_interaction_logic.py) ·
[research page](../../projects/fastapi-playwright/src/day62_research_page.py) ·
[browser task](../../projects/fastapi-playwright/src/day62_browser_task.py) ·
[tests](../../projects/fastapi-playwright/tests/) ·
[cheat sheet](../../cheat_sheets/fastapi.md) ·
[interview](../../interview/fastapi.md) ·
Previous: [Day61 lesson](day61-object-storage-provider-adapter-and-opentelemetry-end-to-end-evidence.md)
