"""Controlled process-crash and restart recovery runtime for Day94."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


SERVER_FIXTURE = (
    Path(__file__).parent / "fixtures" / "day93_mcp_streamable_http_server.py"
)
WORKER_FIXTURE = Path(__file__).parent / "fixtures" / "day94_restart_worker.py"
DIRECT_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Day94RestartRecoveryIntegrationTests(unittest.TestCase):
    server: subprocess.Popen[bytes]
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        port = unused_loopback_port()
        cls.base_url = f"http://127.0.0.1:{port}"
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        cls.server = subprocess.Popen(
            [sys.executable, str(SERVER_FIXTURE), "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=environment,
        )
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                stderr = cls.server.stderr.read().decode("utf-8", "replace")
                raise RuntimeError(f"controlled MCP server exited: {stderr}")
            try:
                with DIRECT_HTTP.open(
                    f"{cls.base_url}/health",
                    timeout=0.2,
                ) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("controlled MCP server was not ready")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.terminate()
        try:
            cls.server.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=3.0)

    @classmethod
    def stats(cls) -> dict[str, int]:
        with DIRECT_HTTP.open(f"{cls.base_url}/stats", timeout=1.0) as response:
            return json.loads(response.read())

    def test_new_process_recovers_marker_without_replaying_tool(self) -> None:
        with tempfile.TemporaryDirectory(prefix="day94-restart-") as temp_dir:
            journal = Path(temp_dir) / "dispatch-marker.json"
            before = self.stats()
            dispatcher = subprocess.Popen(
                [
                    sys.executable,
                    str(WORKER_FIXTURE),
                    "--mode",
                    "dispatch",
                    "--journal",
                    str(journal),
                    "--base-url",
                    self.base_url,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=dict(os.environ),
            )
            deadline = time.monotonic() + 10.0
            entered = False
            while time.monotonic() < deadline:
                if dispatcher.poll() is not None:
                    stderr = dispatcher.stderr.read().decode("utf-8", "replace")
                    self.fail(f"dispatch worker exited before crash window: {stderr}")
                current = self.stats()
                if (
                    journal.exists()
                    and current["controlled_service_calls"]
                    > before["controlled_service_calls"]
                ):
                    entered = True
                    break
                time.sleep(0.05)
            self.assertTrue(entered, "dispatch worker never reached controlled Tool")

            dispatcher.terminate()
            try:
                dispatcher.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                dispatcher.kill()
                dispatcher.wait(timeout=3.0)
            if dispatcher.stderr is not None:
                dispatcher.stderr.close()

            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                settled = self.stats()
                if (
                    settled["completed_calls"] + settled["cancelled_calls"]
                    > before["completed_calls"] + before["cancelled_calls"]
                ):
                    break
                time.sleep(0.05)
            calls_before_recovery = self.stats()["controlled_service_calls"]

            recovered_process = subprocess.run(
                [
                    sys.executable,
                    str(WORKER_FIXTURE),
                    "--mode",
                    "recover",
                    "--journal",
                    str(journal),
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                env=dict(os.environ),
                timeout=10.0,
            )
            recovered = json.loads(recovered_process.stdout)
            calls_after_recovery = self.stats()["controlled_service_calls"]

            self.assertEqual(recovered["operation_id"], "op-report-42")
            self.assertEqual(recovered["idempotency_key"], "idem-report-42")
            self.assertEqual(recovered["attempt_number"], 1)
            self.assertEqual(
                recovered["protocol_request_id"],
                "mcp-request-94-1",
            )
            self.assertEqual(recovered["transport_generation"], 1)
            self.assertEqual(
                recovered["recovery_outcome"],
                "RECONCILIATION_REQUIRED",
            )
            self.assertEqual(
                recovered["execution_certainty"],
                "POSSIBLY_EXECUTED",
            )
            self.assertEqual(recovered["authority_observation"], "STILL_PENDING")
            self.assertEqual(
                recovered["schedule_outcome"],
                "NEXT_QUERY_SCHEDULED",
            )
            self.assertEqual(recovered["original_tool_calls"], 0)
            self.assertEqual(recovered["committer_calls"], 0)
            self.assertEqual(calls_after_recovery, calls_before_recovery)


if __name__ == "__main__":
    unittest.main()
