"""Day62 — the reliable async browser task (real Playwright, imported lazily).

Ownership model (taught in class):
  * the ``Browser`` is process/Worker-scoped and REUSED across tasks;
  * every task creates and OWNS its own ``BrowserContext`` (the per-task state + fault-isolation
    boundary); the Context owns its ``Page``;
  * the task closes its Context in ``finally`` — on success AND on failure — and NEVER closes an
    independent sibling Context.

Reliability rules enforced here:
  * NO fixed ``sleep`` — wait on observable conditions (overlay ``data-state=ready``, then the
    business result text). Auto-waiting proves ACTIONABILITY; the final assertion proves the
    BUSINESS FACT.
  * NO ``force=True`` — never punch through an overlay/actionability failure; wait for the
    observable ready condition instead.
  * NO DOM mutation to manufacture success — the task only drives user-equivalent events and
    asserts the page's OWN rendered result.
  * If the business assertion passed but ``context.close()`` fails, the task is INCOMPLETE, not
    fully successful. If the operation AND cleanup both fail, the ORIGINAL operation error is
    primary and the cleanup failure is recorded as diagnostics (see ``classify_task_result``).

``playwright`` is imported INSIDE the function so this module imports (and ``py_compile``s)
without the package; the real run needs ``playwright`` + a Chromium install (see the
design/runbook). Evidence tier for a real run: ``EXECUTED_LOCAL_RUNTIME`` (specific browser
interaction facts) — NOT auth isolation, queue integration, artifact flow, or production.
"""

from __future__ import annotations

from day62_interaction_logic import TaskReport, classify_task_result
from day62_research_page import (
    INPUT_TESTID,
    RESULTS_TESTID,
    SUBMIT_TESTID,
)

# Default action budget: how long the actionability/assertion waits may take before the task
# times out (a real, bounded failure). Tunable per call; never a fixed sleep.
DEFAULT_ACTION_BUDGET_MS = 5_000


async def run_research_task(
    browser: object,
    url: str,
    query: str,
    *,
    action_budget_ms: int = DEFAULT_ACTION_BUDGET_MS,
) -> TaskReport:
    """Run one authorized research task against a REUSED ``browser``.

    Steps: new Context (owned by THIS task) -> new Page -> navigate -> wait for the page's OWN
    ready state -> fill the Company textbox -> click Search (actionability wait) -> assert the
    business result text within the budget. The Context is always closed in ``finally``; the
    ORIGINAL operation error is preserved if cleanup also fails."""
    from playwright.async_api import expect  # lazy import; real run only

    operation_error = None
    cleanup_error = None
    context = await browser.new_context()  # type: ignore[attr-defined]
    try:
        page = await context.new_page()
        await page.goto(url)

        # Wait for the PAGE's own readiness (overlay cleared) — never a fixed sleep, never force.
        overlay = page.get_by_test_id("loading-overlay")
        await expect(overlay).to_have_attribute("data-state", "ready", timeout=action_budget_ms)

        # Scoped, stable Locators: role/accessible name and a maintained data-testid contract.
        form = page.get_by_role("form", name="Company research")
        await form.get_by_role("textbox", name="Company").fill(query)
        await form.get_by_test_id(SUBMIT_TESTID).click()  # actionability wait, no force=True

        # BUSINESS assertion (not just actionability): the page's own rendered result text.
        results = page.get_by_test_id(RESULTS_TESTID)
        await expect(results).to_have_text(f"Results for {query}", timeout=action_budget_ms)
    except Exception as op_err:  # timeout / crash / precondition -> unknown or failed op
        operation_error = f"{type(op_err).__name__}: {op_err}"
    finally:
        try:
            await context.close()
        except Exception as close_err:  # cleanup failure is recorded, never hides the op error
            cleanup_error = f"{type(close_err).__name__}: {close_err}"

    return classify_task_result(operation_error, cleanup_error)


# Re-exported so tests can assert the task depends on the stable contract, not brittle CSS.
LOCATOR_CONTRACT = {
    "input_testid": INPUT_TESTID,
    "submit_testid": SUBMIT_TESTID,
    "results_testid": RESULTS_TESTID,
}
