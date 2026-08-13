"""Day62 — pure decision logic for reliable async browser interaction (standard library only).

The DECISION CORE for Day62, separated from the real Playwright/Chromium runtime so the RULES
are unit-testable WITHOUT a browser, a display, or the Playwright package. It encodes the
Day62 model taught in class:

  * a task's outcome combines the BUSINESS operation result AND the Context CLEANUP result —
    a passed assertion with a failed ``context.close()`` is INCOMPLETE, not fully successful;
  * when the operation AND cleanup both fail, the ORIGINAL operation error is primary and the
    cleanup failure is additional diagnostics (never the reported cause);
  * timeout / login redirect / Page crash mean UNKNOWN outcome or a FAILED PRECONDITION — never
    business "no result" and never permission for a blind retry;
  * an asserted empty result IS a real business fact (a different thing from "unknown").

Evidence tier: functions here are ``EXECUTED_LOCAL_RUNTIME`` when driven by
``tests/test_day62_interaction_logic.py``. They prove the RULES only — NOT real Chromium
actionability, real navigation, or Python ``finally`` cleanup against a live browser (that is a
real Playwright run; see the design/runbook — NOT RUN by the updating agent).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# 1) Task outcome = business operation result AND Context cleanup result.
# ---------------------------------------------------------------------------
class TaskStatus(str, Enum):
    SUCCESS = "success"                 # business asserted AND Context cleanup completed
    FAILED = "failed"                   # the business operation failed (cleanup ok or not)
    INCOMPLETE = "incomplete"           # business asserted but cleanup failed -> not fully successful


@dataclass(frozen=True)
class TaskReport:
    status: TaskStatus
    primary_error: Optional[str]        # the reported cause (the ORIGINAL operation error if any)
    diagnostics: List[str] = field(default_factory=list)  # extra context (e.g. cleanup failure)


def classify_task_result(
    operation_error: Optional[str], cleanup_error: Optional[str]
) -> TaskReport:
    """Combine the business operation and the Context cleanup into ONE honest outcome.

    * no error, clean cleanup            -> SUCCESS.
    * operation failed (cleanup ok/not)  -> FAILED, primary = the operation error; a cleanup
      failure is added as diagnostics but NEVER replaces the original cause.
    * operation ok BUT cleanup failed    -> INCOMPLETE (a passed assertion with a failed
      ``context.close()`` must not be reported as fully successful).
    """
    if operation_error is not None:
        diags: List[str] = []
        if cleanup_error is not None:
            diags.append(f"context_cleanup_failed: {cleanup_error}")
        return TaskReport(TaskStatus.FAILED, primary_error=operation_error, diagnostics=diags)
    if cleanup_error is not None:
        return TaskReport(
            TaskStatus.INCOMPLETE,
            primary_error=f"context_cleanup_failed: {cleanup_error}",
            diagnostics=["business_assertion_passed_but_cleanup_failed"],
        )
    return TaskReport(TaskStatus.SUCCESS, primary_error=None)


# ---------------------------------------------------------------------------
# 2) Interaction signals -> outcome class (never "no result", never blind-retry permission).
# ---------------------------------------------------------------------------
class InteractionOutcome(str, Enum):
    BUSINESS_RESULT = "business_result"          # a business fact was asserted (e.g. results shown)
    BUSINESS_NO_RESULT = "business_no_result"    # an ASSERTED empty result — a real business fact
    UNKNOWN = "unknown"                          # timeout / Page crash -> outcome unknown
    PRECONDITION_FAILED = "precondition_failed"  # login redirect -> session/auth precondition failed


def classify_interaction_signal(signal: str) -> InteractionOutcome:
    """Map a raw interaction signal to an outcome class.

    A client-side ``timeout`` or a ``page_crash`` proves NOTHING about the business result — it
    is UNKNOWN (reuse Day61's rule: timeout is not proof of non-execution). A ``login_redirect``
    is a failed session/auth PRECONDITION, not a business answer. Only an assertion on the
    rendered result yields ``business_result`` / ``business_no_result``.
    """
    normalized = signal.strip().lower()
    if normalized in ("timeout", "action_timeout", "page_crash", "navigation_timeout"):
        return InteractionOutcome.UNKNOWN
    if normalized in ("login_redirect", "auth_redirect", "session_expired"):
        return InteractionOutcome.PRECONDITION_FAILED
    if normalized in ("results_rendered", "business_result"):
        return InteractionOutcome.BUSINESS_RESULT
    if normalized in ("empty_results_rendered", "no_results_rendered"):
        return InteractionOutcome.BUSINESS_NO_RESULT
    return InteractionOutcome.UNKNOWN


def may_blind_retry(outcome: InteractionOutcome) -> bool:
    """An UNKNOWN or a failed PRECONDITION never authorizes a blind retry (a duplicate action
    could double a side effect). Only an explicit recovery/reconciliation policy (Day65) may
    decide a safe retry. An asserted business result/no-result is terminal — nothing to retry."""
    return False


# ---------------------------------------------------------------------------
# 3) Actionability budget: fixed sleep guesses; a bounded budget is a real contract.
# ---------------------------------------------------------------------------
def overlay_budget_ok(overlay_delay_ms: int, action_budget_ms: int) -> bool:
    """The page's overlay clears after ``overlay_delay_ms``; the action may wait up to
    ``action_budget_ms``. If the overlay outlasts the budget, the click cannot become
    actionable in time and the task must TIME OUT (a real, bounded failure) — never a fixed
    sleep guess and never ``force=True`` to punch through the overlay."""
    if overlay_delay_ms < 0 or action_budget_ms < 0:
        raise ValueError("delays and budgets must be non-negative")
    return overlay_delay_ms <= action_budget_ms


# ---------------------------------------------------------------------------
# 4) Locator contract preference (role/name > scoped test-id > brittle CSS/nth).
# ---------------------------------------------------------------------------
class LocatorStrategy(str, Enum):
    ROLE_NAME = "role_name"              # role + accessible name (preferred)
    TEST_ID = "test_id"                 # a maintained data-testid contract (when necessary)
    CSS_DYNAMIC = "css_dynamic"         # dynamic/implementation CSS classes (avoid)
    NTH_POSITIONAL = "nth_positional"   # positional nth() as a default (avoid)


_PREFERENCE = {
    LocatorStrategy.ROLE_NAME: 0,
    LocatorStrategy.TEST_ID: 1,
    LocatorStrategy.CSS_DYNAMIC: 2,
    LocatorStrategy.NTH_POSITIONAL: 3,
}


def locator_is_stable(strategy: LocatorStrategy) -> bool:
    """Stability comes from a MAINTAINED contract (role/accessible name, or a stable
    ``data-testid``), not from a CSS path or a positional index that tracks implementation
    details and breaks on markup churn."""
    return strategy in (LocatorStrategy.ROLE_NAME, LocatorStrategy.TEST_ID)


def prefer_locator(a: LocatorStrategy, b: LocatorStrategy) -> LocatorStrategy:
    """Return the more stable of two strategies (role/name first, then test-id)."""
    return a if _PREFERENCE[a] <= _PREFERENCE[b] else b
