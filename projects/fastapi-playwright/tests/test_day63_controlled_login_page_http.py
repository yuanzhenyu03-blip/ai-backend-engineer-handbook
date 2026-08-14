"""Day63 — EXECUTED_LOCAL_RUNTIME test: the controlled account page over REAL HTTP loopback.

Starts the synthetic account page on 127.0.0.1 and fetches it with stdlib urllib — a real HTTP
request/response, no browser. Proves the page contract the isolation suite depends on: the account
page exposes stable ``principal-id`` / ``organization-id`` facts; ``login_redirect`` mode returns a
302 to ``/login``; ``unapproved_origin`` mode emits a page-owned attempt to reach a different
Origin. All identity values are SYNTHETIC. It does NOT prove Chromium state isolation (that is the
gated real-browser suite — NOT RUN without Playwright).
"""

import threading
import urllib.request

from day63_controlled_login_page import (
    ORG_TESTID,
    PRINCIPAL_TESTID,
    build_server,
)


def _serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _get(url, allow_redirects=True):
    # urllib follows redirects by default; use a no-redirect opener when we want to see the 302.
    if allow_redirects:
        with urllib.request.urlopen(url, timeout=2.0) as r:
            return r.status, r.read().decode("utf-8")

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(url, timeout=2.0) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_account_page_exposes_stable_identity_facts():
    server, base = build_server(port=0, mode="account")
    _serve(server)
    try:
        status, body = _get(f"{base}/account")
        assert status == 200
        assert f'data-testid="{PRINCIPAL_TESTID}">prin_synthetic_0001<' in body
        assert f'data-testid="{ORG_TESTID}">org_synthetic_0001<' in body
    finally:
        server.shutdown()


def test_login_redirect_mode_returns_302_to_login():
    server, base = build_server(port=0, mode="login_redirect")
    _serve(server)
    try:
        status, _ = _get(f"{base}/account?mode=login_redirect", allow_redirects=False)
        assert status == 302
    finally:
        server.shutdown()


def test_unapproved_origin_mode_emits_page_owned_navigation():
    server, base = build_server(port=0, mode="unapproved_origin",
                                unapproved_origin="http://unapproved.example.test")
    _serve(server)
    try:
        status, body = _get(f"{base}/account?mode=unapproved_origin")
        assert status == 200
        assert "window.open(" in body and "unapproved.example.test" in body
    finally:
        server.shutdown()
