"""Separate Day94 dispatch/recovery worker for controlled restart tests."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_mcp_capstone import (
    CapstoneCommitter,
    CapstoneReconciliationCycle,
    CapstoneRecoveryCoordinator,
)
from agent_mcp_orchestrator import AgentMCPOrchestrator
from agent_mcp_recovery import RestartAwareDispatchJournal
from examples.day94_agent_mcp_capstone import orchestration_input, ready_store
from mcp_protocol_model import CURRENT_SPECIFICATION_VERSION, MCPRequestBinding, MCPRequestDTO
from mcp_reconciliation import (
    AuthoritativeOperationStatus,
    AuthoritativeResultEvidence,
    BoundedReconciliationPolicy,
    ReconciliationScheduleState,
)
from mcp_sdk_private_adapter import SDKPrivateMCPClientAdapter


class JournaledSlowSDKTransport:
    def __init__(self, base_url: str, journal: RestartAwareDispatchJournal, store) -> None:
        self._base_url = base_url
        self._journal = journal
        self._store = store

    def execute(self, *, identity, tool_name, attempt):
        marker = self._store.read(identity.operation_id)
        if marker is None:
            raise RuntimeError("durable marker missing before transport")
        self._journal.save(marker)
        return asyncio.run(
            self._execute(identity=identity, tool_name=tool_name, attempt=attempt)
        )

    async def _execute(self, *, identity, tool_name, attempt):
        request = MCPRequestDTO(
            specification_version=CURRENT_SPECIFICATION_VERSION,
            protocol_request_id=attempt.key.protocol_request_id,
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": {
                    "query": "day94 restart crash window",
                    "delay_ms": 2000,
                },
            },
            observed_server_capabilities=frozenset({"tools"}),
        )
        binding = MCPRequestBinding(
            protocol_request_id=attempt.key.protocol_request_id,
            application_operation_id=identity.operation_id,
            expected_method="tools/call",
            request_fingerprint="day94-restart-request",
            tenant_id=identity.tenant_id,
            resource_id=identity.resource_id,
            idempotency_key=identity.idempotency_key,
        )
        async with httpx2.AsyncClient(trust_env=False) as http_client:
            async with SDKPrivateMCPClientAdapter(
                f"{self._base_url}/mcp",
                read_timeout_seconds=10.0,
                http_client=http_client,
            ) as adapter:
                permit = adapter.issue_preflight_permit(
                    "tools/call",
                    tool_name=tool_name,
                    arguments=request.params["arguments"],
                )
                return await adapter.exchange(request, binding, permit)


class NotFoundAuthority:
    def query(self, *, binding):
        return AuthoritativeResultEvidence(
            binding=binding,
            status=AuthoritativeOperationStatus.NOT_FOUND,
            evidence_source="controlled-restart-authority",
        )


class NoopAlerts:
    def emit(self, alert) -> None:
        raise AssertionError("first recovery query must remain within budget")


def dispatch(base_url: str, journal_path: Path) -> None:
    request = orchestration_input()
    store = ready_store(request)
    AgentMCPOrchestrator(
        dispatch_store=store,
        transport=JournaledSlowSDKTransport(
            base_url,
            RestartAwareDispatchJournal(journal_path),
            store,
        ),
        committer=CapstoneCommitter(store),
    ).run(request)


def recover(journal_path: Path) -> None:
    marker = RestartAwareDispatchJournal(journal_path).load()
    recovery = CapstoneRecoveryCoordinator().plan(marker)
    cycle = CapstoneReconciliationCycle().run_once(
        recovery,
        authority=NotFoundAuthority(),
        policy=BoundedReconciliationPolicy(
            base_delay_seconds=1.0,
            jitter_ratio=0.0,
        ),
        state=ReconciliationScheduleState(
            recovery.binding,
            queries_used=0,
            maximum_queries=3,
            deadline=200.0,
        ),
        now=100.0,
        operation_ref="safe-restart-ref",
        alerts=NoopAlerts(),
    )
    print(
        json.dumps(
            {
                "operation_id": recovery.binding.operation_id,
                "idempotency_key": recovery.binding.idempotency_key,
                "attempt_number": recovery.attempt_number,
                "protocol_request_id": recovery.protocol_request_id,
                "transport_generation": recovery.transport_generation,
                "recovery_outcome": recovery.outcome.value,
                "execution_certainty": recovery.failure.execution_certainty.value,
                "authority_observation": cycle.observation.kind.value,
                "schedule_outcome": cycle.schedule.outcome.value,
                "original_tool_calls": cycle.original_tool_calls,
                "committer_calls": cycle.committer_calls,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dispatch", "recover"), required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--base-url")
    args = parser.parse_args()
    if args.mode == "dispatch":
        if not args.base_url:
            raise ValueError("dispatch mode requires --base-url")
        dispatch(args.base_url, args.journal)
    else:
        recover(args.journal)


if __name__ == "__main__":
    main()
