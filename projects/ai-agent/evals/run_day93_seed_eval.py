"""Deterministic Day93 remote-lifecycle seed evaluation."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_client_transport import DispatchCertainty  # noqa: E402
from mcp_jwks_lifecycle import (  # noqa: E402
    JWKSRefreshUnavailable,
    RefreshingJWKSResolver,
)
from mcp_reconciliation import (  # noqa: E402
    ApplicationOperationBinding,
    AuthoritativeOperationStatus,
    AuthoritativeResultEvidence,
    BoundedReconciliationPolicy,
    ComplianceOutcome,
    InMemoryReconciliationStore,
    ReconciliationCommitter,
    ReconciliationScheduleState,
    ReconciliationScheduler,
    authoritative_not_executed_evidence,
)
from mcp_remote_failure_adapter import (  # noqa: E402
    ApplicationRemoteFailureAdapter,
    AuthenticatedRemoteContext,
    ControlledRemoteFailureContract,
    RemoteFailureClaim,
)
from mcp_remote_lifecycle import (  # noqa: E402
    CancellationObservation,
    DeadlineBudget,
    ExecutionCertainty,
    FailureEvidence,
    FailureKind,
    FailurePhase,
    cancellation_failure_evidence,
    classify_lifecycle_outcome,
)
from mcp_remote_session import (  # noqa: E402
    RemoteCorrelationRegistry,
    RemoteRequestBinding,
    RemoteRequestKey,
)
from mcp_retry_policy import (  # noqa: E402
    BoundedRetryPolicy,
    RetryContext,
    plan_retry_attempt,
)
from mcp_server_lifecycle import MCPServerLifecycle  # noqa: E402
from mcp_versioning import (  # noqa: E402
    VersionedApplicationPermit,
    negotiate_generation,
    validate_versioned_permit,
)


def result(outcome: str, *, committer_calls: int = 0) -> dict[str, object]:
    return {
        "outcome": outcome,
        "handler_calls": 0,
        "service_calls": 0,
        "committer_calls": committer_calls,
    }


def failure(
    *,
    kind: FailureKind = FailureKind.CONNECT_TIMEOUT,
    phase: FailurePhase = FailurePhase.CONNECT,
    dispatch: DispatchCertainty = DispatchCertainty.PROVEN_NOT_SENT,
    execution: ExecutionCertainty = ExecutionCertainty.PROVEN_NOT_EXECUTED,
) -> FailureEvidence:
    return FailureEvidence(
        "op-report-42",
        "idem-report-42",
        "request-1",
        1,
        phase,
        kind,
        dispatch,
        execution,
        "day93-seed",
    )


def retry_context(**overrides: object) -> RetryContext:
    values: dict[str, object] = {
        "now": 100.0,
        "deadline": 108.0,
        "retries_used": 0,
        "max_retries": 2,
        "caller_intent_active": True,
        "authorization_current": True,
        "capacity_admitted": True,
        "circuit_allows_request": True,
    }
    values.update(overrides)
    return RetryContext(**values)  # type: ignore[arg-type]


def matched_remote_failure(*, verified: bool) -> ExecutionCertainty:
    registry = RemoteCorrelationRegistry()
    generation = registry.begin_generation()
    key = RemoteRequestKey(generation, "request-1")
    registry.bind(RemoteRequestBinding(
        key, "op-report-42", "idem-report-42", 1
    ))
    mapped = ApplicationRemoteFailureAdapter(
        ControlledRemoteFailureContract("research-mcp.internal")
    ).translate(
        RemoteFailureClaim(503, "CAPACITY_REJECTED"),
        context=AuthenticatedRemoteContext(
            "research-mcp.internal", identity_verified=verified
        ),
        correlation=registry.correlate_response(key),
    )
    assert mapped.evidence is not None
    return mapped.evidence.execution_certainty


class NotExecutedAuthority:
    def query(self, *, binding: ApplicationOperationBinding):
        return AuthoritativeResultEvidence(
            binding,
            AuthoritativeOperationStatus.NOT_EXECUTED,
            "controlled-authority",
        )


class UnknownAuthority:
    def query(self, *, binding: ApplicationOperationBinding):
        return AuthoritativeResultEvidence(
            binding,
            AuthoritativeOperationStatus.UNKNOWN,
            "controlled-authority",
        )


class Alerts:
    def __init__(self) -> None:
        self.items: list[object] = []

    def emit(self, alert: object) -> None:
        self.items.append(alert)


class FailingRefresh:
    def refresh_unknown_key(self, key_id: str) -> bytes | None:
        raise JWKSRefreshUnavailable(key_id)


class Cancellation:
    def cancel(self, operation_id: str) -> None:
        pass


class Pending:
    def mark_pending(self, operation_id: str) -> None:
        pass


def evaluate(category: str) -> dict[str, object]:
    if category == "connect_timeout_before_dispatch":
        decision = BoundedRetryPolicy().decide(failure(), retry_context())
        return result(decision.kind.value)
    if category == "read_timeout_possible_execution":
        observed = failure(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            dispatch=DispatchCertainty.POSSIBLY_SENT,
            execution=ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        return result(classify_lifecycle_outcome(observed).value)
    if category in {"cancellation_before_dispatch", "cancellation_after_dispatch"}:
        before = category.endswith("before_dispatch")
        observed = cancellation_failure_evidence(CancellationObservation(
            "op-report-42",
            "idem-report-42",
            "request-1",
            1,
            DispatchCertainty.PROVEN_NOT_SENT if before else DispatchCertainty.PROVEN_SENT,
            remote_task_cancelled=not before,
            evidence_source="day93-seed",
        ))
        return result(classify_lifecycle_outcome(observed).value)
    if category == "parent_deadline":
        timeout = DeadlineBudget(108.0).stage_timeout(
            now=100.0, configured_timeout=30.0
        )
        return result(str(timeout))
    if category == "retry_identity":
        observed = failure()
        decision = BoundedRetryPolicy().decide(observed, retry_context())
        attempt = plan_retry_attempt(
            observed, decision, new_protocol_request_id="request-2"
        )
        invariant = (
            attempt.operation_id == observed.operation_id
            and attempt.idempotency_key == observed.idempotency_key
            and attempt.protocol_request_id != observed.protocol_request_id
            and attempt.attempt_number == 2
        )
        return result("SAME_OPERATION_FRESH_PROTOCOL_REQUEST" if invariant else "BROKEN")
    if category == "retry_budget_exhausted":
        decision = BoundedRetryPolicy().decide(
            failure(), retry_context(retries_used=2)
        )
        return result(decision.kind.value)
    if category == "stale_reconnect_response":
        registry = RemoteCorrelationRegistry()
        first = registry.begin_generation()
        key = RemoteRequestKey(first, "request-1")
        registry.bind(RemoteRequestBinding(
            key, "op-report-42", "idem-report-42", 1
        ))
        registry.begin_generation()
        return result(registry.correlate_response(key).outcome.value)
    if category == "incompatible_version":
        negotiation = negotiate_generation(
            generation=1,
            client_versions=("2026-07-28",),
            server_versions=frozenset({"2025-11-25"}),
            server_capabilities=frozenset({"tools"}),
        )
        return result(negotiation.outcome.value)
    if category == "capability_downgrade":
        negotiation = negotiate_generation(
            generation=2,
            client_versions=("2026-07-28", "2025-11-25"),
            server_versions=frozenset({"2025-11-25"}),
            server_capabilities=frozenset({"resources"}),
        )
        permit = VersionedApplicationPermit(
            2, "2025-11-25", frozenset({"tools"}), 4,
            "tools/call", "tenant-a", "report-42"
        )
        return result(validate_versioned_permit(
            negotiation, permit, requested_method="tools/call"
        ).outcome.value)
    if category == "trusted_capacity_rejection":
        return result(matched_remote_failure(verified=True).value)
    if category == "untrusted_remote_failure":
        return result(matched_remote_failure(verified=False).value)
    if category == "jwks_refresh_outage":
        decision = RefreshingJWKSResolver({}, FailingRefresh()).resolve("kid-new")
        return result(str(decision.http_status))
    if category == "reconciliation_not_executed":
        observed = failure(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            dispatch=DispatchCertainty.POSSIBLY_SENT,
            execution=ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        binding = ApplicationOperationBinding(
            "op-report-42", "idem-report-42", "tenant-a", "report-42"
        )
        proposal = ReconciliationScheduler(
            NotExecutedAuthority()
        ).reconcile_once(observed, binding=binding)
        store = InMemoryReconciliationStore()
        store.add_pending(binding)
        committed = ReconciliationCommitter(store).commit(
            proposal, expected_version=1, authorization_valid_at_effect=True
        )
        retry_input = authoritative_not_executed_evidence(
            committed, original_failure=observed
        )
        decision = BoundedRetryPolicy().decide(retry_input, retry_context())
        assert decision.eligible
        assert committed.record is not None
        assert committed.record.compliance_outcome is ComplianceOutcome.NOT_APPLICABLE
        return result("NOT_EXECUTED_THEN_POLICY", committer_calls=1)
    if category == "reconciliation_unknown_alert":
        observed = failure(
            kind=FailureKind.READ_TIMEOUT,
            phase=FailurePhase.READ,
            dispatch=DispatchCertainty.POSSIBLY_SENT,
            execution=ExecutionCertainty.POSSIBLY_EXECUTED,
        )
        binding = ApplicationOperationBinding(
            "op-report-42", "idem-report-42", "tenant-a", "report-42"
        )
        proposal = ReconciliationScheduler(
            UnknownAuthority()
        ).reconcile_once(observed, binding=binding)
        alerts = Alerts()
        scheduled = BoundedReconciliationPolicy().advance(
            proposal,
            ReconciliationScheduleState(binding, 0, 1, 110.0),
            now=100.0,
            operation_ref="opref-controlled",
            alerts=alerts,
        )
        assert len(alerts.items) == 1 and scheduled.state.pending_reconciliation
        return result(scheduled.outcome.value)
    if category == "graceful_shutdown_unknown":
        lifecycle = MCPServerLifecycle(Cancellation(), Pending())
        lifecycle.begin_request("op-report-42")
        lifecycle.start_shutdown()
        report = lifecycle.expire_drain_timeout()
        return result(report.outcome.value, committer_calls=report.committer_calls)
    raise ValueError(f"unknown category: {category}")


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    return [
        name
        for name in (
            "outcome", "handler_calls", "service_calls", "committer_calls"
        )
        if actual[name] != case[f"expected_{name}"]
    ]


def main() -> int:
    path = Path(__file__).with_name("day93_mcp_remote_lifecycle_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not 12 <= len(cases) <= 20:
        raise ValueError("Day93 seed requires 12 to 20 independent cases")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Day93 seed case IDs must be unique")
    failed = 0
    for case in cases:
        if case["case_version"] != 1:
            raise ValueError("unsupported case version")
        try:
            actual = evaluate(str(case["category"]))
            differences = grade(case, actual)
            status = "FAIL" if differences else "PASS"
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            actual = {"error_class": type(error).__name__}
            differences = ["exception"]
            status = "FAIL"
        failed += status == "FAIL"
        print(json.dumps({
            "case_id": case["case_id"],
            "result": status,
            "differences": differences,
            "actual": actual,
        }, sort_keys=True))
    print(json.dumps({
        "cases": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
        "case_version": 1,
        "evidence_level": "EXECUTED_LOCAL_RUNTIME",
    }, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
