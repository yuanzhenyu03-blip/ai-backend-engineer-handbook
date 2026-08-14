"""Day64 — a controlled localhost dynamic-report page + JSON API (a real process over HTTP).

Models the classroom scenario: a near-empty SPA shell that fetches ``/api/reports/{id}`` (which may
be ``generating`` before it is ``ready``) and exposes ``POST /api/exports`` returning a terminal
``export_id``. It serves SYNTHETIC data only — no real reports, credentials, Cookies, target URLs, or
sensitive payloads; bound to 127.0.0.1, no external network.

The page is genuinely DYNAMIC: its OWN (synthetic, no-sensitive-data) JavaScript fetches
``/api/reports/42``, renders the loading/ready state, renders a LIMITED, rounded/virtualized DOM (the
first 20 rows at 2-decimal precision while the JSON carries all 500 rows at full precision — so the
network JSON is the primary structured-data candidate and the DOM only corroborates), and exposes a
triggerable Export action that ``POST``s ``/api/exports`` and shows the returned ``export_id``. This
is intended to serve a FUTURE real-Playwright local test (NOT RUN this round). The browserless
HTTP-loopback test drives only the JSON API/contract (no JavaScript executes under urllib).
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPORT_ID = "42"
FULL_ROWS = 500


def _report_payload(status: str) -> dict:
    if status != "ready":
        return {"report_id": REPORT_ID, "status": status, "rows": []}
    rows = [{"row_id": i, "score": round(0.123456 + i * 0.000001, 6), "label": f"item-{i}"}
            for i in range(FULL_ROWS)]
    return {"report_id": REPORT_ID, "status": "ready", "rows": rows}


def _spa_shell() -> str:
    """A genuinely dynamic, SYNTHETIC SPA. Its page-owned JS fetches the report API, renders the
    loading/ready state + a limited rounded/virtualized DOM, and triggers a real Export POST. No
    sensitive data, no external network."""
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Report SPA (synthetic)</title></head>
<body>
  <div id="app" data-testid="report-app" data-state="loading">
    <span data-testid="report-status">loading</span>
    <span data-testid="source-row-count"></span>
    <ul data-testid="report-rows"></ul>
    <button data-testid="export-btn" disabled>Export CSV</button>
    <span data-testid="export-id"></span>
    <span data-testid="export-status"></span>
  </div>
  <script>
    // PAGE-OWNED behavior (synthetic). Read the desired status from the URL for deterministic tests.
    const params = new URLSearchParams(location.search);
    const status = params.get('status') || 'generating';
    const app = document.querySelector('[data-testid="report-app"]');
    const statusEl = document.querySelector('[data-testid="report-status"]');
    const rowsEl = document.querySelector('[data-testid="report-rows"]');
    const srcCountEl = document.querySelector('[data-testid="source-row-count"]');
    const exportBtn = document.querySelector('[data-testid="export-btn"]');
    const exportIdEl = document.querySelector('[data-testid="export-id"]');
    const exportStatusEl = document.querySelector('[data-testid="export-status"]');

    fetch('/api/reports/42?status=' + encodeURIComponent(status))
      .then(function (r) { return r.json(); })
      .then(function (report) {
        if (report.status !== 'ready') {
          app.setAttribute('data-state', 'generating');
          statusEl.textContent = 'generating';
          return; // NOT ready -> no rows, Export stays disabled
        }
        app.setAttribute('data-state', 'ready');
        statusEl.textContent = 'ready';
        srcCountEl.textContent = String(report.rows.length); // full source count (500) from the JSON
        // DOM is LOSSY: only the first 20 rows, score rounded to 2 decimals (network JSON is primary).
        report.rows.slice(0, 20).forEach(function (row) {
          const li = document.createElement('li');
          li.textContent = row.label + ': ' + Number(row.score).toFixed(2);
          rowsEl.appendChild(li);
        });
        exportBtn.disabled = false;
      });

    exportBtn.addEventListener('click', function () {
      // OUR stable action identity, created before the request completes.
      const clientRequestId = 'crq-' + Date.now();
      exportStatusEl.textContent = 'exporting';
      fetch('/api/exports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_id: '42', client_request_id: clientRequestId })
      })
        .then(function (r) { return r.json(); })
        .then(function (out) {
          exportIdEl.textContent = out.export_id;      // correlatable back to our client_request_id
          exportStatusEl.textContent = 'exported';
        });
    });
  </script>
</body>
</html>
"""


def make_handler(report_status: str = "generating"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_a) -> None:  # quiet
            pass

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/report"):
                return self._send(200, _spa_shell().encode("utf-8"), "text/html; charset=utf-8")
            if parsed.path == f"/api/reports/{REPORT_ID}":
                params = parse_qs(parsed.query)
                status = params.get("status", [report_status])[0]
                return self._send(200, json.dumps(_report_payload(status)).encode("utf-8"),
                                  "application/json")
            self._send(404, b"", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}
            if parsed.path == "/api/exports":
                # strict action identity echoed back: report_id + client_request_id -> export_id
                out = {
                    "export_id": "exp-" + str(body.get("client_request_id", "x")),
                    "report_id": body.get("report_id"),
                    "client_request_id": body.get("client_request_id"),
                    "status": "exporting",
                }
                return self._send(200, json.dumps(out).encode("utf-8"), "application/json")
            self._send(404, b"", "text/plain")

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 0, *, report_status: str = "generating"):
    server = ThreadingHTTPServer((host, port), make_handler(report_status))
    base_url = f"http://{host}:{server.server_address[1]}"
    return server, base_url


def main() -> None:  # pragma: no cover
    import os

    port = int(os.environ.get("DAY64_REPORT_PORT", "8064"))
    status = os.environ.get("DAY64_REPORT_STATUS", "generating")
    server, base = build_server("127.0.0.1", port, report_status=status)
    print(f"Day64 report page on {base}/report ; API {base}/api/reports/{REPORT_ID}?status={status}")
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
