"""Day93 protocol version and capability downgrade tests."""
import unittest

from mcp_versioning import (
    VersionNegotiationOutcome,
    VersionedApplicationPermit,
    VersionedPermitOutcome,
    negotiate_generation,
    validate_versioned_permit,
)


CURRENT = "2026-07-28"
OLDER = "2025-11-25"


def permit(
    *,
    generation: int,
    version: str,
    capabilities: frozenset[str] = frozenset({"tools"}),
) -> VersionedApplicationPermit:
    return VersionedApplicationPermit(
        generation=generation,
        negotiated_version=version,
        capabilities=capabilities,
        authorization_revision=7,
        method="tools/call",
        tenant_id="tenant-a",
        resource_id="research-report-42",
    )


class Day93MCPVersioningTests(unittest.TestCase):
    def test_common_lower_version_requires_fresh_generation_permit(self) -> None:
        old_permit = permit(generation=1, version=CURRENT)
        reconnected = negotiate_generation(
            generation=2,
            client_versions=(CURRENT, OLDER),
            server_versions=frozenset({OLDER}),
            server_capabilities=frozenset({"tools"}),
        )

        decision = validate_versioned_permit(
            reconnected,
            old_permit,
            requested_method="tools/call",
        )

        self.assertEqual(reconnected.negotiated_version, OLDER)
        self.assertTrue(reconnected.requires_fresh_preflight)
        self.assertEqual(decision.outcome, VersionedPermitOutcome.STALE_GENERATION)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)

    def test_no_common_version_rejects_before_handler(self) -> None:
        result = negotiate_generation(
            generation=2,
            client_versions=(CURRENT,),
            server_versions=frozenset({OLDER}),
            server_capabilities=frozenset({"tools"}),
        )

        self.assertEqual(result.outcome, VersionNegotiationOutcome.INCOMPATIBLE)
        self.assertEqual(result.error_code, -32022)
        self.assertEqual(result.supported_versions, (OLDER,))
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)

    def test_capability_downgrade_cannot_reuse_old_tools_permission(self) -> None:
        negotiation = negotiate_generation(
            generation=2,
            client_versions=(CURRENT,),
            server_versions=frozenset({CURRENT}),
            server_capabilities=frozenset({"resources"}),
        )
        freshly_scoped_but_forged_tools_permit = permit(
            generation=2,
            version=CURRENT,
            capabilities=frozenset({"tools"}),
        )

        decision = validate_versioned_permit(
            negotiation,
            freshly_scoped_but_forged_tools_permit,
            requested_method="tools/call",
        )

        self.assertEqual(
            decision.outcome,
            VersionedPermitOutcome.CAPABILITY_REJECTED,
        )
        self.assertEqual(decision.handler_calls, 0)

    def test_fresh_exact_permit_is_admitted_after_negotiation(self) -> None:
        negotiation = negotiate_generation(
            generation=2,
            client_versions=(CURRENT, OLDER),
            server_versions=frozenset({OLDER}),
            server_capabilities=frozenset({"tools"}),
        )
        fresh_permit = permit(generation=2, version=OLDER)

        decision = validate_versioned_permit(
            negotiation,
            fresh_permit,
            requested_method="tools/call",
        )

        self.assertEqual(decision.outcome, VersionedPermitOutcome.ADMITTED)


if __name__ == "__main__":
    unittest.main()
