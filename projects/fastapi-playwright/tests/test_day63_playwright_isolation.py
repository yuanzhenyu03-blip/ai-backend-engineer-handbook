"""Day63 — BrowserContext isolation + real popup/redirect observation, driven through the Gate.

This module is the real-Chromium suite ONLY, GATED on the ``playwright`` package via a module-level
``importorskip``. When ``playwright`` is absent, THIS FILE (and only this file) is skipped — the pure
Session-Gate tests and the HTTP-loopback page-contract tests still run. A real local run here is
``EXECUTED_LOCAL_RUNTIME`` (BrowserContext state isolation + real popup/navigation observation + no
auto-login after a login redirect); it is NOT integration or production, and it is NOT RUN by the
updating agent (no ``playwright`` in this environment). The live classroom artifact was
``CONCEPTUAL_STATIC``. These assertions are therefore NOT claimed as verified until Playwright/Chromium
actually run them.
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
    JobRequest,
    ObservedIdentity,
    Outcome,
    SessionBinding,
    SessionMeta,
    TaskCompletion,
    TaskDeps,
    run_task_authorization,
)

UNAPPROVED = "http://unapproved.example.test"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


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
    return SessionMeta("active", now + 1000, 1, "att-1", "tok-1", now + 1000)


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


def test_unapproved_origin_popup_observed_stops_closes_no_publish():  # pragma: no cover - gated
    # A real popup to an UNAPPROVED Origin, observed by the Context, is fed to the Gate through the
    # orchestrator: outcome SECURITY_FAILURE, nothing published, and the Context is closed.
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="unapproved_origin", unapproved_origin=UNAPPROVED)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state = {"published": False, "context_closed": False}

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx = await browser.new_context()

                def read_credential(ref):
                    return {"cookies": [], "origins": []}

                def create_context(_filtered):
                    return ctx  # the real, already-created Context

                def probe_identity(_c):
                    return ObservedIdentity(False, "prin_synthetic_0001", "org_synthetic_0001")

                def observe_origin(_c):
                    # navigate; the page's OWN script opens a popup to the UNAPPROVED Origin, which
                    # we observe and return as the current business-relevant Origin.
                    async def _nav():
                        page = await ctx.new_page()
                        async with ctx.expect_page() as popup_info:
                            await page.goto(f"{base}/account?mode=unapproved_origin")
                        popup = await popup_info.value
                        return _origin_of(popup.url)
                    return _run(_nav())

                def publish_result(_c):
                    state["published"] = True

                def close_context(_c):
                    state["context_closed"] = True
                    _run(ctx.close())

                deps = TaskDeps(read_credential, create_context, probe_identity, observe_origin,
                                publish_result, close_context)
                now = 1_000
                return run_task_authorization(_job(base), _binding(base), _meta(now), deps,
                                              now=now, worker_token="tok-1")
            finally:
                await browser.close()

    try:
        report = _run(_go())
        assert report.outcome is Outcome.SECURITY_FAILURE
        assert report.published is False and state["published"] is False   # NO business result
        assert state["context_closed"] is True                             # Context closed
        assert report.status is TaskCompletion.FAILED
    finally:
        server.shutdown()


def test_login_redirect_yields_precondition_failed_no_auto_login():  # pragma: no cover - gated
    # A Task Context redirected to login must NOT auto-login: no principal fact, redirect observed,
    # and the Gate yields AUTHENTICATION_PRECONDITION_FAILED with no publish.
    from playwright.async_api import async_playwright

    server, base = build_server(port=0, mode="login_redirect")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state = {"published": False, "context_closed": False, "auto_logged_in": None}

    async def _go():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                ctx = await browser.new_context()

                def read_credential(ref):
                    return {"cookies": [], "origins": []}

                def create_context(_filtered):
                    return ctx

                def probe_identity(_c):
                    async def _probe():
                        page = await ctx.new_page()
                        await page.goto(f"{base}/account?mode=login_redirect")
                        on_login = await page.get_by_test_id("login-form").count()
                        principal = await page.get_by_test_id("principal-id").count()
                        # no auto-login: we landed on the login form and there is NO principal fact
                        state["auto_logged_in"] = principal > 0
                        return ObservedIdentity(login_redirect=on_login > 0, principal_id=None,
                                                organization_id=None)
                    return _run(_probe())

                def observe_origin(_c):
                    return base  # not reached (identity fails first)

                def publish_result(_c):
                    state["published"] = True

                def close_context(_c):
                    state["context_closed"] = True
                    _run(ctx.close())

                deps = TaskDeps(read_credential, create_context, probe_identity, observe_origin,
                                publish_result, close_context)
                now = 1_000
                return run_task_authorization(_job(base), _binding(base), _meta(now), deps,
                                              now=now, worker_token="tok-1")
            finally:
                await browser.close()

    try:
        report = _run(_go())
        assert report.outcome is Outcome.AUTHENTICATION_PRECONDITION_FAILED
        assert report.published is False and state["published"] is False
        assert state["auto_logged_in"] is False        # no silent re-authentication
        assert state["context_closed"] is True
    finally:
        server.shutdown()
