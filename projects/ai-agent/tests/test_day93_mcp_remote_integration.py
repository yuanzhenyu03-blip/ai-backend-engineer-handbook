"""Real MCP 2.2.0 Streamable HTTP tests over an independent process."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

import httpx2
from mcp_client_transport import DispatchCertainty
from mcp_protocol_model import (
    CURRENT_SPECIFICATION_VERSION,
    MCPRequestBinding,
    MCPRequestDTO,
    ProtocolOutcome,
)
from mcp_remote_lifecycle import ExecutionCertainty, FailureKind, FailurePhase
from mcp_sdk_private_adapter import SDKPrivateMCPClientAdapter


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "day93_mcp_streamable_http_server.py"
)
DIRECT_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Day93MCPRemoteIntegrationTests(unittest.IsolatedAsyncioTestCase):
    process: subprocess.Popen[bytes]
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = unused_loopback_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        cls.process = subprocess.Popen(
            [sys.executable, str(FIXTURE), "--port", str(cls.port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=environment,
        )
        deadline = time.monotonic() + 15.0
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                stderr = cls.process.stderr.read().decode("utf-8", "replace")
                raise RuntimeError(f"controlled MCP server exited: {stderr}")
            try:
                with DIRECT_HTTP.open(
                    f"{cls.base_url}/health",
                    timeout=0.2,
                ) as response:
                    if response.status == 200:
                        return
            except OSError as error:
                last_error = error
                time.sleep(0.05)
        cls.process.terminate()
        try:
            cls.process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=3.0)
        stderr = cls.process.stderr.read().decode("utf-8", "replace")
        raise RuntimeError(
            "controlled MCP Streamable HTTP server was not ready; "
            f"last_error={last_error!r}; stderr={stderr}"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        try:
            cls.process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=3.0)

    @classmethod
    def stats(cls) -> dict[str, int]:
        with DIRECT_HTTP.open(
            f"{cls.base_url}/stats",
            timeout=1.0,
        ) as response:
            return json.loads(response.read())

    @staticmethod
    def request(request_id: str, delay_ms: int) -> MCPRequestDTO:
        return MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=request_id,
            method="tools/call",
            params={
                "name": "research.lookup",
                "arguments": {
                    "query": "remote lifecycle",
                    "delay_ms": delay_ms,
                },
            },
            client_capabilities=frozenset(),
            observed_server_capabilities=frozenset({"tools"}),
        )

    @staticmethod
    def binding(request_id: str) -> MCPRequestBinding:
        return MCPRequestBinding(
            protocol_request_id=request_id,
            application_operation_id=f"op-{request_id}",
            expected_method="tools/call",
            request_fingerprint=f"fingerprint-{request_id}",
            tenant_id="tenant-a",
            resource_id="research-report-42",
            idempotency_key=f"idem-{request_id}",
        )

    async def test_real_streamable_http_success(self) -> None:
        before = self.stats()
        request = self.request("day93-http-success", delay_ms=0)
        binding = self.binding("day93-http-success")

        async with httpx2.AsyncClient(trust_env=False) as http_client:
            async with SDKPrivateMCPClientAdapter(
                f"{self.base_url}/mcp",
                read_timeout_seconds=2.0,
                http_client=http_client,
            ) as adapter:
                permit = adapter.issue_preflight_permit(
                    "tools/call",
                    tool_name="research.lookup",
                    arguments=request.params["arguments"],
                )
                exchange = await adapter.exchange(request, binding, permit)

        after = self.stats()
        self.assertIsNotNone(exchange.response)
        self.assertIsNone(exchange.observation)
        self.assertEqual(
            after["controlled_service_calls"],
            before["controlled_service_calls"] + 1,
        )
        self.assertEqual(
            after["completed_calls"],
            before["completed_calls"] + 1,
        )

    async def test_real_read_timeout_after_service_entry_is_unknown(self) -> None:
        before = self.stats()
        request = self.request("day93-http-timeout", delay_ms=500)
        binding = self.binding("day93-http-timeout")

        async with httpx2.AsyncClient(trust_env=False) as http_client:
            async with SDKPrivateMCPClientAdapter(
                f"{self.base_url}/mcp",
                read_timeout_seconds=0.05,
                http_client=http_client,
            ) as adapter:
                permit = adapter.issue_preflight_permit(
                    "tools/call",
                    tool_name="research.lookup",
                    arguments=request.params["arguments"],
                )
                exchange = await adapter.exchange(
                    request,
                    binding,
                    permit,
                    attempt_number=1,
                )

        for _ in range(20):
            after = self.stats()
            if (
                after["controlled_service_calls"]
                > before["controlled_service_calls"]
                and (
                    after["completed_calls"] > before["completed_calls"]
                    or after["cancelled_calls"] > before["cancelled_calls"]
                )
            ):
                break
            await asyncio.sleep(0.05)

        self.assertIsNotNone(exchange.observation)
        self.assertEqual(exchange.observation.outcome, ProtocolOutcome.OUTCOME_UNKNOWN)
        self.assertIsNotNone(exchange.failure_evidence)
        self.assertEqual(exchange.failure_evidence.phase, FailurePhase.READ)
        self.assertEqual(exchange.failure_evidence.kind, FailureKind.READ_TIMEOUT)
        self.assertEqual(
            exchange.failure_evidence.dispatch_certainty,
            DispatchCertainty.POSSIBLY_SENT,
        )
        self.assertEqual(
            exchange.failure_evidence.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertEqual(
            after["controlled_service_calls"],
            before["controlled_service_calls"] + 1,
        )
        # In this real SDK/ASGI path, aborting the HTTP response stream does
        # not cancel the already-entered Tool coroutine; it completes after
        # the caller has timed out.  Either outcome would remain unknown, but
        # this observed result proves cancellation is not a rollback signal.
        self.assertEqual(
            after["completed_calls"],
            before["completed_calls"] + 1,
        )
        self.assertEqual(after["cancelled_calls"], before["cancelled_calls"])


if __name__ == "__main__":
    unittest.main()
