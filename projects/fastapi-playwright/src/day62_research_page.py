"""Day62 — a controlled localhost HTTP research page (a real process, served over HTTP).

Why a local HTTP server and not a ``file://`` page: HTTP models route/query/request/response
behavior faithfully and lets us inject a controlled, bounded delay via a query parameter, which
is exactly what a reliable-interaction lesson needs. It is served on 127.0.0.1 only, contains no
secrets, and talks to no external network.

The page is PAGE-OWNED: its OWN JavaScript starts in a loading state with a blocking overlay,
removes the overlay after ``overlay_delay_ms`` and marks the form ready, handles the Search
click, and then ASYNCHRONOUSLY renders ``Results for <query>``. Playwright must NEVER mutate the
DOM to manufacture success — it only drives the same events a user would and asserts the page's
own rendered result.

Contract elements the browser task depends on (stable Locator contract):
  * a Company textbox   — role ``textbox``, accessible name ``Company`` (``data-testid=company-input``);
  * a Search button     — role ``button``, accessible name ``Search`` (``data-testid=company-search-submit``);
  * a results region    — role ``status`` (``data-testid=search-results``), initially empty;
  * a loading overlay   — ``data-testid=loading-overlay`` with ``data-state`` = ``loading`` -> ``ready``.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

# The stable Locator contract (shared with the browser task and asserted by tests).
SUBMIT_TESTID = "company-search-submit"
INPUT_TESTID = "company-input"
RESULTS_TESTID = "search-results"
OVERLAY_TESTID = "loading-overlay"
DEFAULT_OVERLAY_DELAY_MS = 800
MAX_OVERLAY_DELAY_MS = 60_000


def _clamp_delay(overlay_delay_ms: int) -> int:
    if overlay_delay_ms < 0:
        return 0
    return min(overlay_delay_ms, MAX_OVERLAY_DELAY_MS)


def render_research_page(overlay_delay_ms: int = DEFAULT_OVERLAY_DELAY_MS) -> str:
    """Return the controlled research page HTML. ``overlay_delay_ms`` is injected into the
    page's OWN script as the loading duration; the result text is rendered by that script on
    the Search click, never pre-baked into the server response (a test asserts the server does
    NOT ship a ``Results for`` string)."""
    delay = _clamp_delay(overlay_delay_ms)
    # NOTE: the results are produced by the page's own JS on click — the server never renders
    # "Results for ..." itself. json.dumps keeps the injected integer a safe numeric literal.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AI Research Browser — Company Lookup</title>
  <style>
    #{OVERLAY_TESTID} {{ position: fixed; inset: 0; background: #eee; }}
    #{OVERLAY_TESTID}[data-state="ready"] {{ display: none; }}
  </style>
</head>
<body>
  <div id="{OVERLAY_TESTID}" data-testid="{OVERLAY_TESTID}" data-state="loading">Loading…</div>

  <main>
    <form id="research-form" aria-label="Company research" data-state="loading">
      <label for="company">Company</label>
      <input id="company" name="company" type="text" data-testid="{INPUT_TESTID}"
             aria-label="Company" disabled />
      <button id="submit" type="button" data-testid="{SUBMIT_TESTID}" disabled>Search</button>
    </form>

    <div role="status" aria-live="polite" data-testid="{RESULTS_TESTID}"></div>
  </main>

  <script>
    // PAGE-OWNED behavior. The overlay blocks interaction until the loading delay elapses.
    const OVERLAY_DELAY_MS = {json.dumps(delay)};
    const overlay = document.querySelector('[data-testid="{OVERLAY_TESTID}"]');
    const form = document.getElementById('research-form');
    const input = document.querySelector('[data-testid="{INPUT_TESTID}"]');
    const submit = document.querySelector('[data-testid="{SUBMIT_TESTID}"]');
    const results = document.querySelector('[data-testid="{RESULTS_TESTID}"]');

    // After the controlled delay, the PAGE removes its own overlay and marks the form ready.
    setTimeout(function () {{
      overlay.setAttribute('data-state', 'ready');
      form.setAttribute('data-state', 'ready');
      input.disabled = false;
      submit.disabled = false;
    }}, OVERLAY_DELAY_MS);

    // The PAGE handles the Search click and ASYNCHRONOUSLY renders the result text.
    submit.addEventListener('click', function () {{
      if (form.getAttribute('data-state') !== 'ready') return;  // not actionable yet
      const query = (input.value || '').trim();
      results.setAttribute('data-state', 'pending');
      setTimeout(function () {{
        results.textContent = 'Results for ' + query;
        results.setAttribute('data-state', 'ready');
      }}, 50);
    }});
  </script>
</body>
</html>
"""


def make_handler(overlay_delay_ms: int = DEFAULT_OVERLAY_DELAY_MS):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # keep test output quiet
            pass

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            parsed = urlparse(self.path)
            if parsed.path not in ("/research", "/"):
                self.send_response(404)
                self.end_headers()
                return
            # A per-request override lets one server serve different delays: /research?overlay_delay_ms=N
            params = parse_qs(parsed.query)
            try:
                delay = int(params.get("overlay_delay_ms", [overlay_delay_ms])[0])
            except (TypeError, ValueError):
                delay = overlay_delay_ms
            body = render_research_page(delay).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 0,
                 *, overlay_delay_ms: int = DEFAULT_OVERLAY_DELAY_MS):
    """Build a ThreadingHTTPServer serving the controlled page. ``port=0`` picks an ephemeral
    port (tests). Returns ``(server, base_url)``."""
    server = ThreadingHTTPServer((host, port), make_handler(overlay_delay_ms))
    base_url = f"http://{host}:{server.server_address[1]}"
    return server, base_url


def main() -> None:  # pragma: no cover
    import os

    port = int(os.environ.get("DAY62_RESEARCH_PORT", "8062"))
    delay = int(os.environ.get("DAY62_OVERLAY_DELAY_MS", str(DEFAULT_OVERLAY_DELAY_MS)))
    server, base_url = build_server("127.0.0.1", port, overlay_delay_ms=delay)
    print(f"Day62 research page on {base_url}/research?overlay_delay_ms={delay}")
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
