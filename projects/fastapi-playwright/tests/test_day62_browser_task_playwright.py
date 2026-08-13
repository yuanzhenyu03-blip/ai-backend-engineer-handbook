"""Day62 — real-Chromium browser-task suite (GATED on the ``playwright`` package).

This module contains ONLY the tests that need a real browser. When ``playwright`` is not
installed, the module-level ``importorskip`` skips THIS FILE ONLY — the static
reliability-contract checks live in ``test_day62_reliability_contract.py`` and still run. A real
local Chromium run of these tests is ``EXECUTED_LOCAL_RUNTIME`` (specific browser-interaction
facts), NOT integration or production. See the design/runbook to run them locally.
"""

import asyncio
import threading

import pytest

# Skip ONLY this real-Chromium module when Playwright is absent (never the static suite).
pytest.importorskip(
    "playwright.async_api",
    reason="playwright not installed — the real-Chromium Day62 suite is EXECUTED_LOCAL_RUNTIME NOT RUN here",
)

from day62_browser_task import run_research_task  # noqa: E402
from day62_interaction_logic import TaskStatus  # noqa: E402
from day62_research_page import build_server  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_success_over_real_chromium():  # pragma: no cover - only when playwright installed
    from playwright.async_api import async_playwright

    server, base_url = build_server(port=0, overlay_delay_ms=200)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                return await run_research_task(
                    browser, f"{base_url}/research?overlay_delay_ms=200", "Acme", action_budget_ms=5000)
            finally:
                await browser.close()

    try:
        report = _run(_go())
        assert report.status is TaskStatus.SUCCESS
    finally:
        server.shutdown()


def test_action_timeout_when_overlay_exceeds_budget():  # pragma: no cover - gated
    from playwright.async_api import async_playwright

    server, base_url = build_server(port=0, overlay_delay_ms=4000)
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
