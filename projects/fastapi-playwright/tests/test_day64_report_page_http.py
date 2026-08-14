"""Day64 — EXECUTED_LOCAL_RUNTIME: the controlled report page + API over REAL HTTP loopback.

Starts the synthetic report server on 127.0.0.1 and drives it with stdlib urllib — a real HTTP
request/response, no browser. Proves the scenario contract the extraction core depends on: the report
API returns `generating` (HTTP 200 but NOT ready) before `ready`; the ready payload carries the full
500 network rows; and `POST /api/exports` echoes the strict action identity (report_id +
client_request_id -> export_id). It does NOT prove real Playwright extraction (NOT RUN).
"""

import json
import threading
import urllib.request

from day64_controlled_report_page import REPORT_ID, build_server


def _serve(status="generating"):
    server, base = build_server(port=0, report_status=status)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base


def _get_json(url):
    with urllib.request.urlopen(url, timeout=2.0) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2.0) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def test_report_api_generating_then_ready_over_http():
    server, base = _serve()
    try:
        status, body = _get_json(f"{base}/api/reports/{REPORT_ID}?status=generating")
        assert status == 200 and body["status"] == "generating" and body["rows"] == []  # HTTP 200 != ready
        status, body = _get_json(f"{base}/api/reports/{REPORT_ID}?status=ready")
        assert status == 200 and body["status"] == "ready" and len(body["rows"]) == 500  # full network rows
        assert set(body["rows"][0].keys()) == {"row_id", "score", "label"}
    finally:
        server.shutdown()


def test_export_echoes_strict_action_identity_over_http():
    server, base = _serve()
    try:
        status, body = _post_json(f"{base}/api/exports",
                                  {"report_id": REPORT_ID, "client_request_id": "crq-1"})
        assert status == 200
        assert body["report_id"] == REPORT_ID and body["client_request_id"] == "crq-1"
        assert body["export_id"] == "exp-crq-1"          # correlatable back to OUR action id
    finally:
        server.shutdown()
