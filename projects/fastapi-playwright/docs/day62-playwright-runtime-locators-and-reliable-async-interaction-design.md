# Day62 — Playwright Runtime, Locators and Reliable Async Interaction (design / runbook)

Connected, runnable Day62 artifact inside the EXISTING `projects/fastapi-playwright/` project
(no new project root). It teaches reliable asynchronous browser interaction: explicit
Browser/Context/Page ownership, a stable Locator contract, actionability waiting vs a business
assertion, and honest timeout/cleanup boundaries. It does NOT implement Day63 auth/storage
state, Day64 network/download/artifact persistence, Day65 recovery/security policy, or Day66
queue-backed integration.

## Files

- `src/day62_interaction_logic.py` — pure decision core (standard library only): task-outcome
  combination (business result AND Context cleanup), timeout/login/crash classification, the
  no-blind-retry rule, the actionability budget, and the Locator stability preference.
- `src/day62_research_page.py` — a controlled localhost HTTP research page (a real process). Its
  OWN JavaScript starts with a blocking overlay/loading state, removes the overlay after a bounded
  `overlay_delay_ms` and marks the form ready, handles the Search click, then ASYNCHRONOUSLY
  renders `Results for <query>`. Playwright never mutates the DOM to fake success.
- `src/day62_browser_task.py` — the async task: accept a REUSED Browser, create ONE Context per
  task, create a Page, use scoped role/test-id Locators, wait for ready/result conditions, never
  fixed sleep or `force=True`, close the Context in `finally`, and preserve the primary operation
  exception when cleanup also fails.
- `tests/test_day62_interaction_logic.py` — pure-logic tests (EXECUTED_LOCAL_RUNTIME).
- `tests/test_day62_research_page_http.py` — REAL HTTP-loopback tests of the page contract
  (EXECUTED_LOCAL_RUNTIME).
- `tests/test_day62_reliability_contract.py` — STATIC reliability-contract checks that inspect the
  task CODE (docstrings/comments stripped); they ALWAYS run, with or without Playwright.
- `tests/test_day62_browser_task_playwright.py` — the real-Chromium suite ONLY, GATED on the
  `playwright` package via a module-level `importorskip` (this file — and only this file — skips
  when the package is absent; NOT RUN there).
- `requirements-day62.txt` — the two clearly separated run scopes.

## Mental model

```text
Browser        = process-level reusable runtime
BrowserContext = per-task state and fault-isolation boundary
Page           = a task's concrete browsing surface

Locator        = repeatable target contract
auto-waiting   = wait until an action can be performed
assertion      = wait until a business fact is true

timeout / login redirect / Page crash = unknown or failed precondition
task success = business result asserted + Context cleanup completed
```

## Ownership + failure boundaries

- The Browser is Worker/process-scoped and reused; every task owns its own Context; the Context
  owns its Page(s). Task success/failure closes its Context in `finally`; the Browser closes on
  Worker drain/stop or a Browser-level failure.
- For the Day62 one-task-one-Context model, discard a Context after a Page failure — task state is
  no longer trustworthy. A Browser failure invalidates every Context/Page; Task A's failure must
  never close an independent Context B.
- Timeout, login redirect, and Page crash = UNKNOWN outcome or a FAILED precondition — never a
  business `no result` and never permission for a blind retry (recovery is Day65).
- If the business assertion passed but `context.close()` fails, the execution is INCOMPLETE (not
  fully successful). If operation AND cleanup both fail, preserve the ORIGINAL operation error and
  record the cleanup failure as additional diagnostics.
- Never use `force=True` to hide an overlay/actionability failure; wait for an observable
  condition (overlay hidden / `data-state=ready`). `networkidle` is not universal business
  readiness.

## Run

```bash
# EXECUTED_LOCAL_RUNTIME (no browser): pure logic + real HTTP-loopback page contract.
cd projects/fastapi-playwright
python3 -m pip install pytest==7.4.3
python3 -m pytest -q tests/
# -> 13 passed, 1 skipped: the real-Chromium MODULE skips (playwright not installed) — honestly
#    NOT RUN — while the pure-logic, HTTP-loopback and STATIC reliability-contract checks all run.

# EXECUTED_LOCAL_RUNTIME with a real browser (OPT-IN):
python3 -m pip install playwright==1.44.0 pytest==7.4.3
python3 -m playwright install chromium
python3 -m pytest -q tests/
```

## Evidence tiers

- `EXECUTED_LOCAL_RUNTIME` (run by the updating agent): `py_compile` + the pure-logic suite + the
  real HTTP-loopback page-contract suite + the STATIC reliability-contract checks (all actually
  collected and run) — **13 passed, 1 skipped**. The 1 skipped item is the real-Chromium module
  `test_day62_browser_task_playwright.py` (no `playwright` package in the agent environment); the
  four static reliability-contract checks are NO LONGER swallowed by that module's skip.
- `EXECUTED_LOCAL_RUNTIME` (classroom, NOT re-run by the agent): a real Chromium opened
  `/research?overlay_delay_ms=800` through the Playwright CLI; a semantic snapshot found the
  Company textbox, Search button and results status; filling `Acme` + clicking the `data-testid`
  button produced the dynamic `Results for Acme`. This proves specific browser-interaction facts
  ONLY.

### NOT RUN

- Python Playwright + Chromium were unavailable to the updating agent, so the Python async
  `finally` cleanup and the blocked-overlay action-timeout negative case were NOT independently
  run here (they are covered by the pure-logic contract and by the gated real-Chromium tests).
- No external site, no auth/session or tenant isolation (Day63), no network/download/Object
  Storage artifact flow (Day64), no recovery/security policy (Day65), no queue-backed Worker
  integration (Day66), no `INTEGRATION_RUNTIME`, and no production validation.

No secrets, credentials, tenant data, login state, real URLs/tokens, or browser screenshots are
committed; the page is served on 127.0.0.1 only.
