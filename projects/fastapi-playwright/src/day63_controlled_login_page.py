"""Day63 — a controlled localhost account/identity page (a real process, served over HTTP).

Supports the real-browser isolation suite (gated) AND a browserless HTTP-loopback contract test.
It serves SYNTHETIC identity facts only — no real credentials, accounts, Origins, tenant data, or
storage-state exports. Bound to 127.0.0.1, no external network.

Modes (via ``?mode=`` or the default at build time):
  * ``account``           -> HTTP 200 account page exposing a STABLE ``data-testid=principal-id`` and
                             ``data-testid=organization-id`` (the positive identity fact to verify).
  * ``login_redirect``    -> HTTP 302 to ``/login`` (models an unauthenticated/expired session).
  * ``unapproved_origin`` -> an account page whose OWN script attempts a navigation/popup to a
                             DIFFERENT (unapproved) Origin — so a Context can OBSERVE the event.

The account page never "logs in" by itself: a Task Context must not silently re-authenticate. The
positive identity fact is a stable principal_id/organization_id, not the absence of a redirect and
not a mutable display name.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PRINCIPAL_TESTID = "principal-id"
ORG_TESTID = "organization-id"
DISPLAY_TESTID = "display-name"

# Synthetic defaults (NOT real identifiers).
DEFAULT_PRINCIPAL_ID = "prin_synthetic_0001"
DEFAULT_ORGANIZATION_ID = "org_synthetic_0001"
DEFAULT_DISPLAY_NAME = "Synthetic Research User"


def render_account_page(
    principal_id: str = DEFAULT_PRINCIPAL_ID,
    organization_id: str = DEFAULT_ORGANIZATION_ID,
    display_name: str = DEFAULT_DISPLAY_NAME,
    *,
    unapproved_origin: str = "",
) -> str:
    """Render the account page exposing the stable identity facts. If ``unapproved_origin`` is set,
    the page's OWN script attempts to open it (a navigation/popup a Context can observe)."""
    popup = ""
    if unapproved_origin:
        popup = (
            "\n    <script>\n"
            f"      // PAGE-OWNED attempt to reach an UNAPPROVED Origin (observed, never allowed).\n"
            f"      window.open({json.dumps(unapproved_origin)}, '_blank');\n"
            "    </script>\n"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8" /><title>Account — synthetic</title></head>
<body>
  <main aria-label="Account">
    <span data-testid="{PRINCIPAL_TESTID}">{principal_id}</span>
    <span data-testid="{ORG_TESTID}">{organization_id}</span>
    <span data-testid="{DISPLAY_TESTID}">{display_name}</span>
  </main>{popup}
</body>
</html>
"""


def make_handler(mode: str = "account", unapproved_origin: str = "http://unapproved.example.test"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # quiet
            pass

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            req_mode = params.get("mode", [mode])[0]
            if parsed.path == "/login":
                body = b"<!doctype html><title>Login</title><form data-testid='login-form'></form>"
                self._send(200, body)
                return
            if req_mode == "login_redirect":
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            if req_mode == "unapproved_origin":
                self._send(200, render_account_page(unapproved_origin=unapproved_origin).encode("utf-8"))
                return
            # default: the account page with stable identity facts
            self._send(200, render_account_page().encode("utf-8"))

        def _send(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 0, *, mode: str = "account",
                 unapproved_origin: str = "http://unapproved.example.test"):
    """Build a ThreadingHTTPServer for the controlled page. ``port=0`` picks an ephemeral port."""
    server = ThreadingHTTPServer((host, port), make_handler(mode, unapproved_origin))
    base_url = f"http://{host}:{server.server_address[1]}"
    return server, base_url


def main() -> None:  # pragma: no cover
    import os

    port = int(os.environ.get("DAY63_LOGIN_PORT", "8063"))
    mode = os.environ.get("DAY63_LOGIN_MODE", "account")
    server, base_url = build_server("127.0.0.1", port, mode=mode)
    print(f"Day63 controlled account page on {base_url}/account?mode={mode}")
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
