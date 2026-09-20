"""Day94 Orchestrator over real MCP 2.2.0 Streamable HTTP transport."""
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

from agent_mcp_capstone import CapstoneCommitter, CapstoneToolResultCandidate
from agent_mcp_orchestrator import (
    AgentMCPOrchestrator,
    CapstoneTransportExchange,
    CapstoneUnknownTransportOutcome,
    OrchestrationOutcome,
)
from examples.day94_agent_mcp_capstone import orchestration_input, ready_store
from mcp_protocol_model import (
    BindingStatus,
    CURRENT_SPECIFICATION_VERSION,
    MCPProtocolBoundary,
    MCPRequestBinding,
    MCPRequestDTO,
    ProtocolOutcome,
)
from mcp_remote_lifecycle import ExecutionCertainty, FailureKind
from mcp_remote_session import (
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)
from mcp_retry_policy import RetryDispatchRecordState
from mcp_sdk_private_adapter import SDKPrivateMCPClientAdapter


FIXTURE = Path(__file__).parent / "fixtures" / "day93_mcp_streamable_http_server.py"
DIRECT_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RealSDKCapstoneTransport:
    """SDK-private Adapter contained behind the Day94 transport port."""

    def __init__(
        self,
        base_url: str,
        *,
        delay_ms: int,
        read_timeout_seconds: float,
    ) -> None:
        self._base_url = base_url
        self._delay_ms = delay_ms
        self._read_timeout_seconds = read_timeout_seconds

    def execute(self, *, identity, tool_name, attempt):
        return asyncio.run(
            self._execute(
                identity=identity,
                tool_name=tool_name,
                attempt=attempt,
            )
        )

    async def _execute(self, *, identity, tool_name, attempt):
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=attempt.key.protocol_request_id,
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": {
                    "query": "day94 real SDK capstone",
                    "delay_ms": self._delay_ms,
                },
            },
            observed_server_capabilities=frozenset({"tools"}),
        )
        protocol_binding = MCPRequestBinding(
            protocol_request_id=attempt.key.protocol_request_id,
            application_operation_id=identity.operation_id,
            expected_method="tools/call",
            request_fingerprint="day94-real-sdk-request",
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            idempotency_key=identity.idempotency_key,
        )
        async with httpx2.AsyncClient(trust_env=False) as http_client:
            async with SDKPrivateMCPClientAdapter(
                f"{self._base_url}/mcp",
                read_timeout_seconds=self._read_timeout_seconds,
                http_client=http_client,
            ) as adapter:
                permit = adapter.issue_preflight_permit(
                    "tools/call",
                    tool_name=tool_name,
                    arguments=request.params["arguments"],
                )
                exchange = await adapter.exchange(
                    request,
                    protocol_binding,
                    permit,
                    attempt_number=attempt.attempt_number,
                )

        if exchange.failure_evidence is not None:
            raise CapstoneUnknownTransportOutcome(
                exchange.failure_evidence,
                handler_calls=1,
                controlled_tool_calls=1,
            )
        assert exchange.response is not None
        boundary = MCPProtocolBoundary(transport=object())  # type: ignore[arg-type]
        boundary.bindings[request.protocol_request_id] = protocol_binding
        boundary.binding_status[request.protocol_request_id] = BindingStatus.PENDING
        observation = boundary.correlate(exchange.response)
        assert observation.outcome is ProtocolOutcome.PROTOCOL_RESULT
        assert observation.payload is not None
        structured = observation.payload.get("structuredContent")
        if not isinstance(structured, dict):
            raise AssertionError("real SDK result lacks structured content")
        source = structured.get("source")
        if not isinstance(source, str) or not source:
            raise AssertionError("real SDK result lacks controlled source")
        return CapstoneTransportExchange(
            correlation=RemoteResponseCorrelation(
                RemoteResponseCorrelationOutcome.MATCHED,
                attempt,
            ),
            observation=observation,
            candidate=CapstoneToolResultCandidate(
                operation_id=identity.operation_id,
                tenant_id=identity.tenant_id,
                resource_id=identity.resource_id,
                tool_name=tool_name,
                external_object_id=source,
            ),
        )


class Day94AgentMCPSDKIntegrationTests(unittest.TestCase):
    process: subprocess.Popen[bytes]
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        port = unused_loopback_port()
        cls.base_url = f"http://127.0.0.1:{port}"
        environment = dict(os.environ)
        environment["PYTHONUNBUFFERED"] = "1"
        cls.process = subprocess.Popen(
            [sys.executable, str(FIXTURE), "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=environment,
        )
        deadline = time.monotonic() + 15.0
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
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("controlled MCP server was not ready")

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
        with DIRECT_HTTP.open(f"{cls.base_url}/stats", timeout=1.0) as response:
            return json.loads(response.read())

    def test_real_sdk_capstone_happy_path_reaches_verified_agent_observation(
        self,
    ) -> None:
        request = orchestration_input()
        store = ready_store(request)
        before = self.stats()

        result = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=RealSDKCapstoneTransport(
                self.base_url,
                delay_ms=0,
                read_timeout_seconds=2.0,
            ),
            committer=CapstoneCommitter(store),
        ).run(request)

        after = self.stats()
        self.assertEqual(result.outcome, OrchestrationOutcome.SUCCEEDED)
        self.assertIsNotNone(result.verified_agent_observation)
        self.assertTrue(result.durable_transition)
        self.assertEqual(
            after["controlled_service_calls"],
            before["controlled_service_calls"] + 1,
        )
        persisted = store.read(request.identity.operation_id)
        assert persisted is not None
        self.assertEqual(persisted.state, RetryDispatchRecordState.COMPLETED)

    def test_real_sdk_capstone_timeout_remains_unknown_after_tool_completes(
        self,
    ) -> None:
        request = orchestration_input()
        store = ready_store(request)
        before = self.stats()

        result = AgentMCPOrchestrator(
            dispatch_store=store,
            transport=RealSDKCapstoneTransport(
                self.base_url,
                delay_ms=500,
                read_timeout_seconds=0.05,
            ),
            committer=CapstoneCommitter(store),
        ).run(request)

        for _ in range(20):
            after = self.stats()
            if after["completed_calls"] > before["completed_calls"]:
                break
            time.sleep(0.05)
        self.assertEqual(
            result.outcome,
            OrchestrationOutcome.PENDING_RECONCILIATION,
        )
        assert result.failure_evidence is not None
        self.assertEqual(result.failure_evidence.kind, FailureKind.READ_TIMEOUT)
        self.assertEqual(
            result.failure_evidence.execution_certainty,
            ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        self.assertIsNone(result.verified_agent_observation)
        self.assertEqual(result.committer_calls, 0)
        self.assertEqual(
            after["controlled_service_calls"],
            before["controlled_service_calls"] + 1,
        )
        self.assertEqual(
            after["completed_calls"],
            before["completed_calls"] + 1,
        )
        persisted = store.read(request.identity.operation_id)
        assert persisted is not None
        self.assertEqual(
            persisted.state,
            RetryDispatchRecordState.DISPATCH_STARTED,
        )


if __name__ == "__main__":
    unittest.main()
