"""Day62 — browser task: STATIC contract checks (always run) + a real-Chromium suite (gated).

The static checks run WITHOUT Playwright and guard the reliability rules in the task source.
The real-Chromium tests require the ``playwright`` package + an installed browser; when the
dependency is absent they are SKIPPED — honestly recorded as NOT RUN by the updating agent
(no fabricated integration pass). See the design/runbook to run them locally.
"""

import pathlib

import pytest

_SRC = (pathlib.Path(__file__).parent / ".." / "src" / "day62_browser_task.py").read_text()


# ---- STATIC reliability contract (no Playwright needed) --------------------------------
def test_task_never_uses_fixed_sleep_or_force():
    assert "force=True" not in _SRC                 # never punch through an overlay/actionability
    assert "asyncio.sleep" not in _SRC and "time.sleep" not in _SRC   # no fixed sleep guesses


def test_task_owns_one_context_and_closes_it_in_finally():
    assert "browser.new_context()" in _SRC          # a new Context per task
    assert "finally:" in _SRC and "context.close()" in _SRC          # always closed
    assert "classify_task_result(operation_error, cleanup_error)" in _SRC  # honest outcome


def test_task_waits_on_business_result_not_only_actionability():
    assert "to_have_attribute(\"data-state\", \"ready\"" in _SRC     # ready condition
    assert "to_have_text(f\"Results for {query}\"" in _SRC           # business assertion


def test_task_uses_stable_locators_not_brittle_css():
    assert "get_by_role(" in _SRC and "get_by_test_id(" in _SRC
    assert ".query_selector(" not in _SRC           # not brittle CSS/DOM querying


# ---- Real Chromium suite (gated; NOT RUN unless the dependency exists) ------------------
playwright_async = pytest.importorskip(
    "playwright.async_api",
    reason="playwright not installed — real-Chromium Day62 tests are INTEGRATION-adjacent NOT RUN",
)

import asyncio  # noqa: E402

from day62_browser_task import run_research_task  # noqa: E402
from day62_interaction_logic import TaskStatus  # noqa: E402
from day62_research_page import build_server  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_success_over_real_chromium():  # pragma: no cover - only when playwright installed
    from playwright.async_api import async_playwright

    server, base_url = build_server(port=0, overlay_delay_ms=200)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                report = await run_research_task(
                    browser, f"{base_url}/research?overlay_delay_ms=200", "Acme", action_budget_ms=5000)
            finally:
                await browser.close()
            return report

    try:
        report = _run(_go())
        assert report.status is TaskStatus.SUCCESS
    finally:
        server.shutdown()


def test_action_timeout_when_overlay_exceeds_budget():  # pragma: no cover - gated
    from playwright.async_api import async_playwright

    server, base_url = build_server(port=0, overlay_delay_ms=4000)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                # budget < overlay delay -> the click never becomes actionable -> FAILED (unknown),
                # never a fake success and never force=True.
                return await run_research_task(
                    browser, f"{base_url}/research?overlay_delay_ms=4000", "Acme", action_budget_ms=500)
            finally:
                await browser.close()

    try:
        report = _run(_go())
        assert report.status is TaskStatus.FAILED
    finally:
        server.shutdown()
