"""Day63 — BrowserContext isolation + real popup/redirect observation, driven through the ASYNC Gate.

Real-Chromium suite ONLY, GATED on the ``playwright`` package via a module-level ``importorskip``.
When ``playwright`` is absent, THIS FILE (and only this file) is skipped — the pure Session-Gate tests
and the HTTP-loopback page-contract tests still run.

Event-loop discipline (the fix): each test runs ONE event loop via ``run_until_complete(_go())`` and
does ALL browser + Gate work inside that single ``async def _go()`` with ``await``. It uses the ASYNC
Gate orchestrator (``run_task_authorization_async`` + ``AsyncTaskDeps``), so nothing calls
``run_until_complete``/``asyncio.run`` from inside a running loop (which would raise
"Cannot run the event loop while another loop is running"). The Gate's safety boundaries are
unchanged — the async twin awaits the same pure decisions.

A real local run here is ``EXECUTED_LOCAL_RUNTIME`` (BrowserContext cookie isolation + real
popup/navigation observation + no auto-login after a login redirect). It is NOT integration or
production. In the UPDATING AGENT'S environment there is no ``playwright`` package, so this module is
SKIPPED and these browser facts are **NOT RUN / NOT verified** until Playwright/Chromium actually run
them. The live classroom artifact was ``CONCEPTUAL_STATIC``.
"""

import asyncio
import threading
from urllib.parse import urlparse

import pytest

# Skip ONLY this real-Chromium module when Playwright is absent (never the static/pure suites).
pytest.importorskip(
    "playwright.async_api",
    reason="playwright not installed — the real-Chromium Day63 isolation suite is EXECUTED_LOCAL_RUNTIME NOT RUN here",
)

from day63_controlled_login_page import build_server  # noqa: E402
from day63_session_gate import (  # noqa: E402
    AsyncTaskDeps,
    JobRequest,
    ObservedIdentity,
    Outcome,
    SessionBinding,
    SessionMeta,
    TaskCompletion,
    run_task_authorization_async,
)

UNAPPROVED = "http://unapproved.example.test"


def _loop_run(coro):
    """Run a coroutine to completion on a fresh loop. There is no running loop at test-function
    scope, so this is the ONE loop for the test; everything inside the coroutine uses ``await``."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _binding(origin: str) -> SessionBinding:
    return SessionBinding(
        tenant_id="tenantB", session_id="sess-B1", target_origin=origin, owner="att-1",
        expected_principal_id="prin_synthetic_0001", expected_organization_id="org_synthetic_0001",
        credential_ref="cred://ref/B1",
    )


def _job(origin: str) -> JobRequest:
    return JobRequest("tenantB", "sess-B1", origin, "att-1")


def _meta(now: int) -> SessionMeta:
    # active, owned by att-1, token tok-1, lease + session not expired -> claim CLAIMED, fence passes.
    return SessionMeta("active", now + 1000, 1, "att-1", "tok-1", now + 1000)


def _serve():
    server, base = build_server(port=0, mode="account")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base


def test_two_contexts_do_not_share_cookies():  # pragma: no cover - only when playwright installed
    from playwright.async_api import async_playwright

    server, base = _serve()

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
        assert _loop_run(_go()) == []            # Context B never sees Context A's cookie
    finally:
        server.shutdown()


def test_unapproved_origin_popup_observed_stops_closes_no_publish():  # pragma: no cover - gated
    # A real popup to an UNAPPROVED Origin, observed by the Context, is fed through the ASYNC Gate:
    # outcome SECURITY_FAILURE, nothing published, and the Context is closed — all in ONE event loop.
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="unapproved_origin", unapproved_origin=UNAPPROVED)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx = await browser.new_context()
                state = {"published": False, "closed": False}

                async def read_credential(ref):
                    return {"cookies": [], "origins": []}

                async def create_context(_filtered):
                    return ctx  # the real, already-created Context

                async def probe_identity(_c):
                    return ObservedIdentity(False, "prin_synthetic_0001", "org_synthetic_0001")

                async def observe_origin(_c):
                    page = await ctx.new_page()
                    async with ctx.expect_page() as popup_info:   # the page opens an unapproved popup
                        await page.goto(f"{base}/account?mode=unapproved_origin")
                    popup = await popup_info.value
                    return _origin_of(popup.url)

                async def publish_result(_c):
                    state["published"] = True

                async def close_context(_c):
                    state["closed"] = True
                    await ctx.close()

                deps = AsyncTaskDeps(read_credential, create_context, probe_identity, observe_origin,
                                     publish_result, close_context)
                now = 1_000
                report = await run_task_authorization_async(
                    _job(base), _binding(base), _meta(now), deps, now=now, worker_token="tok-1")
                return report, state
            finally:
                await browser.close()

    try:
        report, state = _loop_run(_go())
        assert report.outcome is Outcome.SECURITY_FAILURE
        assert report.published is False and state["published"] is False   # NO business result
        assert state["closed"] is True                                     # Context closed
        assert report.status is TaskCompletion.FAILED
    finally:
        server.shutdown()


def test_login_redirect_yields_precondition_failed_no_auto_login():  # pragma: no cover - gated
    # A Task Context redirected to login must NOT auto-login: no principal fact, redirect observed,
    # and the ASYNC Gate yields AUTHENTICATION_PRECONDITION_FAILED with no publish.
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="login_redirect")
    threading.Thread(target=server.serve_forever, daemon=True).start()

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx = await browser.new_context()
                state = {"published": False, "closed": False, "auto_logged_in": None}

                async def read_credential(ref):
                    return {"cookies": [], "origins": []}

                async def create_context(_filtered):
                    return ctx

                async def probe_identity(_c):
                    page = await ctx.new_page()
                    await page.goto(f"{base}/account?mode=login_redirect")
                    on_login = await page.get_by_test_id("login-form").count()
                    principal = await page.get_by_test_id("principal-id").count()
                    state["auto_logged_in"] = principal > 0   # no silent re-auth -> no principal fact
                    return ObservedIdentity(login_redirect=on_login > 0, principal_id=None,
                                            organization_id=None)

                async def observe_origin(_c):
                    return base  # not reached (identity fails first)

                async def publish_result(_c):
                    state["published"] = True

                async def close_context(_c):
                    state["closed"] = True
                    await ctx.close()

                deps = AsyncTaskDeps(read_credential, create_context, probe_identity, observe_origin,
                                     publish_result, close_context)
                now = 1_000
                report = await run_task_authorization_async(
                    _job(base), _binding(base), _meta(now), deps, now=now, worker_token="tok-1")
                return report, state
            finally:
                await browser.close()

    try:
        report, state = _loop_run(_go())
        assert report.outcome is Outcome.AUTHENTICATION_PRECONDITION_FAILED
        assert report.published is False and state["published"] is False
        assert state["auto_logged_in"] is False        # no silent re-authentication
        assert state["closed"] is True
    finally:
        server.shutdown()
