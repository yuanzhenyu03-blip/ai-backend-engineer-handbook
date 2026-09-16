"""Day93 JWKS refresh, cache and fail-closed tests."""
import unittest

from mcp_client_transport import DispatchCertainty
from mcp_jwks_lifecycle import (
    JWKSRefreshUnavailable,
    KeyResolutionOutcome,
    RefreshingJWKSResolver,
)
from mcp_observability import BoundedMetricRecorder
from mcp_remote_failure_adapter import (
    ApplicationRemoteFailureAdapter,
    AuthenticatedRemoteContext,
    ControlledRemoteFailureContract,
    RemoteFailureClaim,
)
from mcp_remote_lifecycle import ExecutionCertainty, FailureKind
from mcp_remote_session import (
    RemoteRequestBinding,
    RemoteRequestKey,
    RemoteResponseCorrelation,
    RemoteResponseCorrelationOutcome,
)


def matched_correlation() -> RemoteResponseCorrelation:
    return RemoteResponseCorrelation(
        RemoteResponseCorrelationOutcome.MATCHED,
        RemoteRequestBinding(
            RemoteRequestKey(2, "mcp-request-93-2"),
            "op-report-42",
            "idem-report-42",
            2,
        ),
    )


class FailingRefresh:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def refresh_unknown_key(self, key_id: str) -> bytes | None:
        self.calls.append(key_id)
        raise JWKSRefreshUnavailable("controlled dependency outage")


class EmptyRefresh:
    def refresh_unknown_key(self, key_id: str) -> bytes | None:
        return None


class Day93MCPJWKSLifecycleTests(unittest.TestCase):
    def test_unknown_key_refresh_failure_returns_503_without_old_authority(self) -> None:
        refresh = FailingRefresh()
        resolver = RefreshingJWKSResolver(
            {"kid-old": b"old-key"},
            refresh,
        )

        decision = resolver.resolve("kid-new")

        self.assertEqual(
            decision.outcome,
            KeyResolutionOutcome.AUTHENTICATION_DEPENDENCY_UNAVAILABLE,
        )
        self.assertEqual(decision.http_status, 503)
        self.assertIsNone(decision.signing_key)
        self.assertFalse(decision.reused_principal)
        self.assertFalse(decision.reused_authorization_permit)
        self.assertEqual(decision.authorization_calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(refresh.calls, ["kid-new"])

    def test_successful_refresh_that_still_lacks_key_is_401(self) -> None:
        resolver = RefreshingJWKSResolver({}, EmptyRefresh())

        decision = resolver.resolve("kid-unknown")

        self.assertEqual(
            decision.outcome,
            KeyResolutionOutcome.UNKNOWN_SIGNING_KEY,
        )
        self.assertEqual(decision.http_status, 401)

    def test_client_adapter_trusts_controlled_pre_handler_503_contract(self) -> None:
        mapped = ApplicationRemoteFailureAdapter(
            ControlledRemoteFailureContract("research-mcp.internal")
        ).translate(
            RemoteFailureClaim(
                503,
                "AUTHENTICATION_DEPENDENCY_UNAVAILABLE",
            ),
            context=AuthenticatedRemoteContext(
                "research-mcp.internal",
                identity_verified=True,
            ),
            correlation=matched_correlation(),
        )

        self.assertEqual(mapped.evidence.kind, FailureKind.JWKS_REFRESH_FAILED)
        self.assertEqual(
            mapped.evidence.dispatch_certainty,
            DispatchCertainty.PROVEN_SENT,
        )
        self.assertEqual(
            mapped.evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )

    def test_jwks_metric_is_bounded_and_does_not_label_key_id(self) -> None:
        metrics = BoundedMetricRecorder()
        labels = {
            "phase": "AUTHENTICATION_DEPENDENCY",
            "failure_kind": "JWKS_REFRESH_FAILED",
            "outcome": "DEPENDENCY_UNAVAILABLE",
        }

        metrics.increment("mcp_jwks_refresh_total", labels)

        self.assertEqual(metrics.value("mcp_jwks_refresh_total", labels), 1)
        with self.assertRaisesRegex(ValueError, "unbounded"):
            metrics.increment(
                "mcp_jwks_refresh_total",
                {"key_id": "kid-new"},
            )


if __name__ == "__main__":
    unittest.main()
