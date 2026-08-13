"""Day62 — STATIC reliability-contract checks for the async browser task.

These run WITHOUT Playwright installed (they scan the task source), so they are always collected
and executed as part of the EXECUTED_LOCAL_RUNTIME suite. They guard the reliability rules that a
real browser run would otherwise be needed to prove: no fixed sleep / no ``force=True``, one
Context per task closed in ``finally``, waiting on the business result (not only actionability),
and stable role/test-id Locators instead of brittle CSS/DOM queries.

The checks inspect CODE, not prose: docstrings and comments are stripped first, so mentioning an
anti-pattern in documentation (``NO force=True``) does not falsely fail the test — only an actual
code use would. The real-Chromium behaviour lives in ``test_day62_browser_task_playwright.py`` and
is gated on the ``playwright`` package; only that file skips when the dependency is absent.
"""

import pathlib
import re

_SRC = (pathlib.Path(__file__).parent / ".." / "src" / "day62_browser_task.py").read_text()


def _code_only(src: str) -> str:
    """Return the source with triple-quoted docstrings/strings and ``#`` comments removed, so a
    negative check matches only real code, never documentation or comments."""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    stripped = []
    for line in src.splitlines():
        hash_at = line.find("#")
        if hash_at != -1:
            line = line[:hash_at]
        stripped.append(line)
    return "\n".join(stripped)


_CODE = _code_only(_SRC)


def test_task_never_uses_fixed_sleep_or_force():
    assert "force=True" not in _CODE                # never punch through an overlay/actionability
    assert "asyncio.sleep" not in _CODE and "time.sleep" not in _CODE   # no fixed sleep guesses


def test_task_owns_one_context_and_closes_it_in_finally():
    assert "browser.new_context()" in _CODE         # a new Context per task
    assert "finally:" in _CODE and "context.close()" in _CODE           # always closed
    assert "classify_task_result(operation_error, cleanup_error)" in _CODE  # honest outcome


def test_task_waits_on_business_result_not_only_actionability():
    assert 'to_have_attribute("data-state", "ready"' in _CODE           # ready condition
    assert 'to_have_text(f"Results for {query}"' in _CODE               # business assertion


def test_task_uses_stable_locators_not_brittle_css():
    assert "get_by_role(" in _CODE and "get_by_test_id(" in _CODE
    assert ".query_selector(" not in _CODE          # not brittle CSS/DOM querying
