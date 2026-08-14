"""Day63 — BrowserContext isolation real-Chromium suite (GATED on the ``playwright`` package).

This module contains ONLY tests that need a real browser. When ``playwright`` is not installed, the
module-level ``importorskip`` skips THIS FILE ONLY — the static gate-source contract checks live in
``test_day63_session_gate.py`` and still run. A real local run here is ``EXECUTED_LOCAL_RUNTIME``
(BrowserContext state isolation + redirect/popup observation + no auto-login); it is NOT integration
or production, and it is NOT RUN by the updating agent. The live classroom artifact was
``CONCEPTUAL_STATIC``.
"""

import asyncio
import threading

import pytest

# Skip ONLY this real-Chromium module when Playwright is absent (never the static/pure suites).
pytest.importorskip(
    "playwright.async_api",
    reason="playwright not installed — the real-Chromium Day63 isolation suite is EXECUTED_LOCAL_RUNTIME NOT RUN here",
)

from day63_controlled_login_page import build_server  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_two_contexts_do_not_share_cookies():  # pragma: no cover - only when playwright installed
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="account")
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx_a = await browser.new_context()
                page_a = await ctx_a.new_page()
                await page_a.goto(f"{base}/account")
                await ctx_a.add_cookies([{"name": "sid", "value": "A", "url": base}])  # synthetic
                ctx_b = await browser.new_context()   # a FRESH Context for another task/tenant
                cookies_b = await ctx_b.cookies(base)
                await ctx_a.close(); await ctx_b.close()
                return cookies_b
            finally:
                await browser.close()

    try:
        assert _run(_go()) == []            # Context B never sees Context A's cookie
    finally:
        server.shutdown()


def test_task_context_stops_on_login_redirect_no_auto_login():  # pragma: no cover - gated
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="login_redirect")
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx = await browser.new_context()
                page = await ctx.new_page()
                await page.goto(f"{base}/account?mode=login_redirect")
                landed_on_login = await page.get_by_test_id("login-form").count()
                await ctx.close()
                return landed_on_login
            finally:
                await browser.close()

    try:
        assert _run(_go()) >= 1            # redirected to login; the Task must stop, not re-auth
    finally:
        server.shutdown()
