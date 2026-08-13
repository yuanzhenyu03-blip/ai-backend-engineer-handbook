"""Day62 — EXECUTED_LOCAL_RUNTIME unit tests for the pure interaction/cleanup decision logic.

Standard-library only. Proves the RULES: task-outcome combination (business + cleanup),
timeout/login/crash classification, no-blind-retry, the actionability budget, and the Locator
stability preference. NOT a browser run (no Chromium, no Playwright, no navigation).
"""

from day62_interaction_logic import (
    InteractionOutcome,
    LocatorStrategy,
    TaskStatus,
    classify_interaction_signal,
    classify_task_result,
    locator_is_stable,
    may_blind_retry,
    overlay_budget_ok,
    prefer_locator,
)


def test_success_requires_business_and_cleanup():
    r = classify_task_result(operation_error=None, cleanup_error=None)
    assert r.status is TaskStatus.SUCCESS and r.primary_error is None


def test_cleanup_failure_after_success_is_incomplete_not_success():
    r = classify_task_result(operation_error=None, cleanup_error="Target closed")
    assert r.status is TaskStatus.INCOMPLETE
    assert "context_cleanup_failed" in r.primary_error
    assert "business_assertion_passed_but_cleanup_failed" in r.diagnostics


def test_operation_error_is_primary_even_when_cleanup_also_fails():
    r = classify_task_result(operation_error="TimeoutError: waiting for ready", cleanup_error="Target closed")
    assert r.status is TaskStatus.FAILED
    assert r.primary_error == "TimeoutError: waiting for ready"   # ORIGINAL op error preserved
    assert any("context_cleanup_failed" in d for d in r.diagnostics)  # cleanup only diagnostics


def test_timeout_and_crash_are_unknown_login_is_precondition():
    assert classify_interaction_signal("timeout") is InteractionOutcome.UNKNOWN
    assert classify_interaction_signal("page_crash") is InteractionOutcome.UNKNOWN
    assert classify_interaction_signal("login_redirect") is InteractionOutcome.PRECONDITION_FAILED
    # an ASSERTED empty result is a real business fact, distinct from "unknown"
    assert classify_interaction_signal("empty_results_rendered") is InteractionOutcome.BUSINESS_NO_RESULT
    assert classify_interaction_signal("results_rendered") is InteractionOutcome.BUSINESS_RESULT


def test_unknown_and_precondition_never_authorize_blind_retry():
    assert may_blind_retry(InteractionOutcome.UNKNOWN) is False
    assert may_blind_retry(InteractionOutcome.PRECONDITION_FAILED) is False
    assert may_blind_retry(InteractionOutcome.BUSINESS_NO_RESULT) is False


def test_overlay_budget_boundary():
    assert overlay_budget_ok(800, 5000) is True
    assert overlay_budget_ok(5000, 5000) is True       # equal is within budget
    assert overlay_budget_ok(6000, 5000) is False      # overlay outlasts budget -> must time out


def test_locator_stability_preference():
    assert locator_is_stable(LocatorStrategy.ROLE_NAME) is True
    assert locator_is_stable(LocatorStrategy.TEST_ID) is True
    assert locator_is_stable(LocatorStrategy.CSS_DYNAMIC) is False
    assert locator_is_stable(LocatorStrategy.NTH_POSITIONAL) is False
    assert prefer_locator(LocatorStrategy.TEST_ID, LocatorStrategy.ROLE_NAME) is LocatorStrategy.ROLE_NAME
    assert prefer_locator(LocatorStrategy.CSS_DYNAMIC, LocatorStrategy.TEST_ID) is LocatorStrategy.TEST_ID
