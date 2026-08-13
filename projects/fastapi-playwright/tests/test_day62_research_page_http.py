"""Day62 — EXECUTED_LOCAL_RUNTIME test: the controlled research page over REAL HTTP loopback.

Starts the page server on 127.0.0.1 (ephemeral port) and fetches it with stdlib urllib — a real
HTTP request/response, no browser. Proves the PAGE-OWNED contract: the overlay + form + button +
results elements and the page's own JS (delay-then-ready, click-then-async-render) are present,
the ``overlay_delay_ms`` query parameter is injected into the page script, and the server does
NOT pre-render the result text (only the page's JS does). It does NOT prove Chromium
actionability or Python cleanup (that is a real Playwright run — NOT RUN here).
"""

import threading
import urllib.request

from day62_research_page import (
    OVERLAY_TESTID,
    RESULTS_TESTID,
    SUBMIT_TESTID,
    build_server,
    render_research_page,
)


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=2.0) as resp:
        return resp.read().decode("utf-8")


def test_page_served_over_http_has_the_stable_contract():
    server, base_url = build_server(port=0, overlay_delay_ms=800)
    _serve(server)
    try:
        body = _get(f"{base_url}/research?overlay_delay_ms=120")
        # stable Locator contract elements
        assert f'data-testid="{OVERLAY_TESTID}"' in body
        assert f'data-testid="{SUBMIT_TESTID}"' in body
        assert f'data-testid="{RESULTS_TESTID}"' in body
        assert 'aria-label="Company"' in body and 'role="status"' in body
        # the per-request overlay_delay_ms is injected into the page's own script
        assert "const OVERLAY_DELAY_MS = 120;" in body
        # page-owned behavior: delay-then-ready + click-then-async-render
        assert "setAttribute('data-state', 'ready')" in body
        assert "addEventListener('click'" in body
        # the SERVER must NOT ship a pre-rendered result — only the page JS renders it
        assert "Results for " not in body.replace("'Results for '", "")
    finally:
        server.shutdown()


def test_render_is_deterministic_and_clamps_negative_delay():
    assert render_research_page(0) == render_research_page(-5)   # negative clamps to 0
    assert "const OVERLAY_DELAY_MS = 0;" in render_research_page(0)
