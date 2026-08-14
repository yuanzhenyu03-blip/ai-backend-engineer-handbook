"""Day64 — a controlled localhost dynamic-report page + JSON API (a real process over HTTP).

Models the classroom scenario: a near-empty SPA shell that fetches ``/api/reports/{id}`` (which may
be ``generating`` before it is ``ready``) and exposes ``POST /api/exports`` returning a terminal
``export_id``. It serves SYNTHETIC data only — no real reports, credentials, Cookies, target URLs, or
sensitive payloads; bound to 127.0.0.1, no external network.

It supports the browserless HTTP-loopback contract test (readiness gating + strict correlation
fields) and, later, a real-Playwright extraction run. The DOM ``rows`` are intentionally rounded /
virtualized while the JSON carries full-precision rows — so tests can assert the network JSON is the
primary structured-data candidate and the DOM only corroborates.
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
    # Near-empty shell; the page's own script would fetch /api/reports/42 and render.
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Report SPA (synthetic)</title></head><body>"
        "<div id='app' data-testid='report-app' data-state='loading'></div>"
        "<script>/* page-owned: fetch('/api/reports/42') then render */</script>"
        "</body></html>"
    )


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
