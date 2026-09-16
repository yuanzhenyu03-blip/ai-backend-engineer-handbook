"""Day93 global and authorized-tenant capacity boundary tests."""
import unittest

from mcp_authorization import ToolAuthorizationPermit
from mcp_client_transport import DispatchCertainty
from mcp_remote_lifecycle import ExecutionCertainty
from mcp_remote_protection import (
    EdgeTransportFacts,
    GlobalLoadSheddingOutcome,
    TenantCapacityAdmission,
    TenantCapacityClass,
    TenantCapacityOutcome,
    admit_global_load,
)


def permit(tenant_id: str) -> ToolAuthorizationPermit:
    return ToolAuthorizationPermit(
        principal_issuer="https://issuer.example",
        principal_subject="researcher-7",
        application_operation_id="op-report-42",
        idempotency_key="idem-report-42",
        tenant_id=tenant_id,
        tool_name="research.lookup",
    )


class Day93MCPRemoteProtectionTests(unittest.TestCase):
    def test_global_shedding_uses_only_cheap_transport_facts(self) -> None:
        decision = admit_global_load(
            EdgeTransportFacts("source-bucket-3", "mcp-http"),
            global_capacity_available=False,
        )

        self.assertEqual(decision.outcome, GlobalLoadSheddingOutcome.SHED)
        self.assertEqual(decision.http_status, 503)
        self.assertEqual(decision.authentication_calls, 0)
        self.assertEqual(decision.authorization_calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)

    def test_payload_tenant_cannot_claim_priority_capacity(self) -> None:
        untrusted_payload_tenant = "tenant-vip"
        admission = TenantCapacityAdmission(
            tenant_classes={
                "tenant-a": TenantCapacityClass.STANDARD,
                "tenant-vip": TenantCapacityClass.PRIORITY,
            },
            available_classes=frozenset({TenantCapacityClass.PRIORITY}),
        )

        decision = admission.admit(
            permit("tenant-a"),
            protocol_request_id="mcp-request-93-1",
            attempt_number=1,
        )

        self.assertEqual(untrusted_payload_tenant, "tenant-vip")
        self.assertEqual(decision.outcome, TenantCapacityOutcome.REJECTED)
        self.assertEqual(decision.capacity_class, TenantCapacityClass.STANDARD)
        self.assertEqual(
            decision.rejection.evidence.dispatch_certainty,
            DispatchCertainty.PROVEN_NOT_SENT,
        )
        self.assertEqual(
            decision.rejection.evidence.execution_certainty,
            ExecutionCertainty.PROVEN_NOT_EXECUTED,
        )
        self.assertEqual(decision.rejection.transport_calls, 0)
        self.assertEqual(decision.rejection.controlled_service_calls, 0)

    def test_authorized_tenant_permit_can_select_priority_capacity(self) -> None:
        admission = TenantCapacityAdmission(
            tenant_classes={"tenant-vip": TenantCapacityClass.PRIORITY},
            available_classes=frozenset({TenantCapacityClass.PRIORITY}),
        )

        decision = admission.admit(
            permit("tenant-vip"),
            protocol_request_id="mcp-request-93-2",
            attempt_number=1,
        )

        self.assertEqual(decision.outcome, TenantCapacityOutcome.ADMITTED)
        self.assertEqual(decision.capacity_class, TenantCapacityClass.PRIORITY)
        self.assertIsNone(decision.rejection)


if __name__ == "__main__":
    unittest.main()
