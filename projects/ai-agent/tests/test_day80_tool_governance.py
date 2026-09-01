import unittest
import os
import sys

DAY66_SRC = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "fastapi-playwright",
        "src",
    )
)
sys.path.insert(0, DAY66_SRC)

from day66_queue_backed_permissioned_worker import (
    ProposalDecision,
    ServerAuthorizedContract,
    ToolCallProposal,
    validate_tool_proposal,
)

from output_tool_contracts import ToolDefinition, ToolRegistry
from tool_governance import (
    AgentToolCatalogEntry,
    AgentObservationStatus,
    ArgumentEnumConstraint,
    BackendResultPhase,
    BoundToolInvocation,
    BackendPreparationStatus,
    CompositePermissionStatus,
    InvocationGovernanceStatus,
    GovernedToolCandidate,
    PermissionLayerResult,
    PolicyEffect,
    SafeToolResult,
    TrustedToolContext,
    build_tool_capability_snapshot,
    check_invocation_governance,
    compose_permission_layers,
    prepare_candidate_for_backend_admission,
    project_backend_result_for_agent,
    translate_snapshot_for_framework,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "report_id": {"type": "string"},
        "target_origin": {"type": "string"},
    },
    "required": ["report_id", "target_origin"],
    "additionalProperties": False,
}

BROWSER_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string"},
        "tenant_id": {"type": "string"},
        "target_origin": {"type": "string"},
        "report_scope": {"type": "string"},
        "idempotency_key": {"type": "string"},
    },
    "required": [
        "operation",
        "tenant_id",
        "target_origin",
        "report_scope",
        "idempotency_key",
    ],
    "additionalProperties": False,
}


class ToolVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry(
            (
                ToolDefinition("publish_report", "v1", SCHEMA),
                ToolDefinition(
                    "browser.export_report", "v1", BROWSER_SCHEMA
                ),
            )
        )
        self.catalog = (
            AgentToolCatalogEntry(
                "publish_report", "v1", "Publish an authorized draft"
            ),
            AgentToolCatalogEntry(
                "browser.export_report", "v1", "Export an authorized report"
            ),
        )

    def context(
        self,
        *grants: str,
        constraints: tuple[ArgumentEnumConstraint, ...] = (),
    ) -> TrustedToolContext:
        return TrustedToolContext(
            tenant_id="tenant-a",
            user_id="user-1",
            role="publisher",
            job_id="J1",
            step_id="S1",
            granted_tool_ids=frozenset(grants),
            argument_enum_constraints=constraints,
        )

    def test_ungranted_tool_is_filtered_before_model_visibility(self) -> None:
        snapshot = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("publish_report@v1"),
        )

        self.assertEqual(
            tuple(tool.name for tool in snapshot.visible_tools),
            ("publish_report",),
        )
        self.assertEqual(
            tuple(
                (item.tool_id, item.visible, item.reason)
                for item in snapshot.decisions
            ),
            (
                (
                    "browser.export_report@v1",
                    False,
                    "NOT_GRANTED_FOR_CONTEXT",
                ),
                ("publish_report@v1", True, "VISIBLE"),
            ),
        )

    def test_disabled_tool_is_not_visible_even_when_policy_granted(self) -> None:
        self.registry.disable("browser.export_report", "v1")
        snapshot = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("browser.export_report@v1"),
        )

        self.assertEqual(snapshot.visible_tools, ())
        self.assertEqual(snapshot.decisions[0].reason, "TOOL_DISABLED")

    def test_same_facts_produce_same_snapshot_identity(self) -> None:
        first = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("publish_report@v1"),
        )
        second = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("publish_report@v1"),
        )

        self.assertEqual(first, second)

    def binding_for(self, snapshot, tool_name="browser.export_report"):
        tool = next(
            item for item in snapshot.visible_tools if item.name == tool_name
        )
        return BoundToolInvocation(
            snapshot_id=snapshot.snapshot_id,
            tenant_id=snapshot.tenant_id,
            user_id=snapshot.user_id,
            role=snapshot.role,
            job_id=snapshot.job_id,
            step_id=snapshot.step_id,
            tool_name=tool.name,
            tool_version=tool.version,
            arguments_schema_sha256=tool.arguments_schema_sha256,
        )

    def test_current_revocation_blocks_old_visible_snapshot(self) -> None:
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("browser.export_report@v1"),
        )

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=self.context(),
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.CURRENT_PERMISSION_REVOKED,
        )

    def test_current_disable_blocks_old_visible_snapshot(self) -> None:
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("browser.export_report@v1"),
        )
        self.registry.disable("browser.export_report", "v1")

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=self.context("browser.export_report@v1"),
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED,
        )

    def test_active_v2_cannot_replace_a_disabled_v1_binding(self) -> None:
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context("browser.export_report@v1"),
        )
        binding = self.binding_for(original)
        self.registry.disable("browser.export_report", "v1")
        registry_with_v2 = ToolRegistry(
            (
                ToolDefinition(
                    "browser.export_report", "v1", BROWSER_SCHEMA
                ),
                ToolDefinition(
                    "browser.export_report", "v2", BROWSER_SCHEMA
                ),
            )
        )
        registry_with_v2.disable("browser.export_report", "v1")
        catalog_with_v2 = self.catalog + (
            AgentToolCatalogEntry(
                "browser.export_report",
                "v2",
                "Export an authorized report using v2",
            ),
        )

        result = check_invocation_governance(
            binding=binding,
            original_snapshot=original,
            current_context=self.context(
                "browser.export_report@v1",
                "browser.export_report@v2",
            ),
            registry=registry_with_v2,
            catalog=catalog_with_v2,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED,
        )
        self.assertEqual(binding.tool_version, "v1")

    def test_unchanged_current_facts_only_allow_progress_to_day74(self) -> None:
        current = self.context("browser.export_report@v1")
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=current,
        )

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=current,
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.ALLOWED_TO_DAY74_ADMISSION,
        )

    def test_step_projection_narrows_origin_without_mutating_base_schema(self) -> None:
        constraint = ArgumentEnumConstraint(
            "browser.export_report@v1",
            "target_origin",
            ("https://reports.example.test:443",),
        )
        snapshot = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context(
                "browser.export_report@v1",
                constraints=(constraint,),
            ),
        )

        tool = snapshot.visible_tools[0]
        self.assertIn(
            '"enum":["https://reports.example.test:443"]',
            tool.arguments_schema_json,
        )
        definition, _ = self.registry.resolve("browser.export_report", "v1")
        assert definition is not None
        self.assertNotIn("enum", definition.arguments_schema["properties"]["target_origin"])
        self.assertNotEqual(
            tool.base_schema_sha256,
            tool.arguments_schema_sha256,
        )

    def test_changed_origin_permission_invalidates_old_schema_binding(self) -> None:
        old_constraint = ArgumentEnumConstraint(
            "browser.export_report@v1",
            "target_origin",
            ("https://reports.example.test:443",),
        )
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=self.context(
                "browser.export_report@v1",
                constraints=(old_constraint,),
            ),
        )
        new_constraint = ArgumentEnumConstraint(
            "browser.export_report@v1",
            "target_origin",
            ("https://archive.example.test:443",),
        )

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=self.context(
                "browser.export_report@v1",
                constraints=(new_constraint,),
            ),
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.SCHEMA_BINDING_MISMATCH,
        )

    def test_projection_cannot_add_unknown_property(self) -> None:
        constraint = ArgumentEnumConstraint(
            "browser.export_report@v1",
            "undeclared_capability",
            ("anything",),
        )

        with self.assertRaisesRegex(ValueError, "cannot add"):
            build_tool_capability_snapshot(
                registry=self.registry,
                catalog=self.catalog,
                context=self.context(
                    "browser.export_report@v1",
                    constraints=(constraint,),
                ),
            )

    def test_duplicate_catalog_identity_is_rejected(self) -> None:
        duplicate = self.catalog + (self.catalog[0],)

        with self.assertRaisesRegex(ValueError, "duplicate Tool catalog"):
            build_tool_capability_snapshot(
                registry=self.registry,
                catalog=duplicate,
                context=self.context("publish_report@v1"),
            )

    def test_removed_catalog_entry_fails_closed_on_current_recheck(self) -> None:
        current = self.context("browser.export_report@v1")
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=current,
        )

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=current,
            registry=self.registry,
            catalog=(self.catalog[0],),
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.CURRENT_REGISTRY_BLOCKED,
        )

    def test_role_change_invalidates_original_binding(self) -> None:
        original_context = self.context("browser.export_report@v1")
        original = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=original_context,
        )
        changed_role = TrustedToolContext(
            tenant_id=original_context.tenant_id,
            user_id=original_context.user_id,
            role="viewer",
            job_id=original_context.job_id,
            step_id=original_context.step_id,
            granted_tool_ids=original_context.granted_tool_ids,
        )

        result = check_invocation_governance(
            binding=self.binding_for(original),
            original_snapshot=original,
            current_context=changed_role,
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            result,
            InvocationGovernanceStatus.ORIGINAL_SNAPSHOT_MISMATCH,
        )


class PermissionCompositionTests(unittest.TestCase):
    @staticmethod
    def layer(
        name: str,
        effect: PolicyEffect,
    ) -> PermissionLayerResult:
        return PermissionLayerResult(name, effect, f"{name}_{effect.value}")

    def test_any_authoritative_deny_blocks_union_of_allows(self) -> None:
        decision = compose_permission_layers(
            (
                self.layer("tenant", PolicyEffect.ALLOW),
                self.layer("user", PolicyEffect.ALLOW),
                self.layer("job", PolicyEffect.ALLOW),
                self.layer("step", PolicyEffect.DENY),
            )
        )

        self.assertIs(decision.status, CompositePermissionStatus.DENIED)
        self.assertEqual(decision.safe_reason, "DENIED_BY_step")

    def test_pre_execution_unknown_is_policy_unavailable_not_reconciliation(self) -> None:
        decision = compose_permission_layers(
            (
                self.layer("tenant", PolicyEffect.ALLOW),
                self.layer("user", PolicyEffect.UNKNOWN),
                self.layer("job", PolicyEffect.ALLOW),
                self.layer("step", PolicyEffect.ALLOW),
            )
        )

        self.assertIs(
            decision.status,
            CompositePermissionStatus.POLICY_UNAVAILABLE,
        )
        self.assertNotIn("RECONCILIATION", decision.status.value)

    def test_all_required_layers_must_allow(self) -> None:
        decision = compose_permission_layers(
            (
                self.layer("tenant", PolicyEffect.ALLOW),
                self.layer("user", PolicyEffect.ALLOW),
                self.layer("job", PolicyEffect.ALLOW),
                self.layer("step", PolicyEffect.ALLOW),
            )
        )

        self.assertIs(decision.status, CompositePermissionStatus.ALLOWED)


class Day66BoundaryReuseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry(
            (
                ToolDefinition("publish_report", "v1", SCHEMA),
                ToolDefinition(
                    "browser.export_report", "v1", BROWSER_SCHEMA
                ),
            )
        )
        self.catalog = (
            AgentToolCatalogEntry(
                "publish_report", "v1", "Publish an authorized draft"
            ),
            AgentToolCatalogEntry(
                "browser.export_report", "v1", "Export an authorized report"
            ),
        )

    def context(self, *grants: str) -> TrustedToolContext:
        return TrustedToolContext(
            tenant_id="tenant-a",
            user_id="user-1",
            role="publisher",
            job_id="J1",
            step_id="S1",
            granted_tool_ids=frozenset(grants),
        )

    @staticmethod
    def binding_for(snapshot):
        tool = next(
            item
            for item in snapshot.visible_tools
            if item.name == "browser.export_report"
        )
        return BoundToolInvocation(
            snapshot_id=snapshot.snapshot_id,
            tenant_id=snapshot.tenant_id,
            user_id=snapshot.user_id,
            role=snapshot.role,
            job_id=snapshot.job_id,
            step_id=snapshot.step_id,
            tool_name=tool.name,
            tool_version=tool.version,
            arguments_schema_sha256=tool.arguments_schema_sha256,
        )

    def browser_arguments(self) -> dict[str, object]:
        return {
            "operation": "browser.export_report",
            "tenant_id": "tenant-a",
            "target_origin": "https://reports.example.test:443",
            "report_scope": "q3",
            "idempotency_key": "idem-1",
        }

    def test_day80_prepares_then_real_day66_boundary_admits(self) -> None:
        current = self.context("browser.export_report@v1")
        snapshot = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=current,
        )
        binding = self.binding_for(snapshot)
        prepared = prepare_candidate_for_backend_admission(
            candidate=GovernedToolCandidate(binding, self.browser_arguments()),
            original_snapshot=snapshot,
            current_context=current,
            registry=self.registry,
            catalog=self.catalog,
        )

        self.assertIs(
            prepared.status,
            BackendPreparationStatus.READY_FOR_BACKEND_ADMISSION,
        )
        arguments = self.browser_arguments()
        day66 = validate_tool_proposal(
            ToolCallProposal(
                is_tool_call=True,
                operation=str(arguments["operation"]),
                tenant_id=str(arguments["tenant_id"]),
                target_origin=str(arguments["target_origin"]),
                report_scope=str(arguments["report_scope"]),
                idempotency_key=str(arguments["idempotency_key"]),
            ),
            ServerAuthorizedContract(
                tenant_id="tenant-a",
                allowed_operation="browser.export_report",
                approved_origin="https://reports.example.test:443",
                allowed_report_scope="q3",
                session_authorized=True,
                approval_granted=True,
                approval_id="approval-1",
            ),
        )
        self.assertIs(day66, ProposalDecision.ACCEPT_NEW)

    def test_day66_current_contract_still_rejects_revoked_approval(self) -> None:
        current = self.context("browser.export_report@v1")
        snapshot = build_tool_capability_snapshot(
            registry=self.registry,
            catalog=self.catalog,
            context=current,
        )
        binding = self.binding_for(snapshot)
        prepared = prepare_candidate_for_backend_admission(
            candidate=GovernedToolCandidate(binding, self.browser_arguments()),
            original_snapshot=snapshot,
            current_context=current,
            registry=self.registry,
            catalog=self.catalog,
        )
        self.assertIs(
            prepared.status,
            BackendPreparationStatus.READY_FOR_BACKEND_ADMISSION,
        )

        arguments = self.browser_arguments()
        day66 = validate_tool_proposal(
            ToolCallProposal(
                is_tool_call=True,
                operation=str(arguments["operation"]),
                tenant_id=str(arguments["tenant_id"]),
                target_origin=str(arguments["target_origin"]),
                report_scope=str(arguments["report_scope"]),
                idempotency_key=str(arguments["idempotency_key"]),
            ),
            ServerAuthorizedContract(
                tenant_id="tenant-a",
                allowed_operation="browser.export_report",
                approved_origin="https://reports.example.test:443",
                allowed_report_scope="q3",
                session_authorized=True,
                approval_granted=False,
            ),
        )
        self.assertIs(day66, ProposalDecision.REJECT_UNAPPROVED)


class SafeToolResultProjectionTests(unittest.TestCase):
    def test_accepted_task_is_not_an_agent_observation(self) -> None:
        decision = project_backend_result_for_agent(
            phase=BackendResultPhase.ACCEPTED,
        )

        self.assertIs(
            decision.status,
            AgentObservationStatus.WAIT_FOR_TERMINAL_RESULT,
        )
        self.assertIsNone(decision.observation)

    def test_unverified_terminal_payload_is_not_an_agent_observation(self) -> None:
        decision = project_backend_result_for_agent(
            phase=BackendResultPhase.UNVERIFIED_TERMINAL,
        )

        self.assertIs(
            decision.status,
            AgentObservationStatus.BLOCKED_UNVERIFIED_RESULT,
        )
        self.assertIsNone(decision.observation)

    def test_only_verified_terminal_safe_result_is_visible(self) -> None:
        safe_result = SafeToolResult(
            tool_call_id="TC1",
            operation_id="OP1",
            result_code="REPORT_EXPORTED",
        )
        decision = project_backend_result_for_agent(
            phase=BackendResultPhase.VERIFIED_TERMINAL,
            verified_safe_result=safe_result,
        )

        self.assertIs(
            decision.status,
            AgentObservationStatus.SAFE_RESULT_READY,
        )
        self.assertEqual(decision.observation, safe_result)


class FrameworkTranslationTests(unittest.TestCase):
    def test_framework_receives_exactly_snapshot_visible_tools(self) -> None:
        registry = ToolRegistry(
            (
                ToolDefinition("browser.export_report", "v1", BROWSER_SCHEMA),
                ToolDefinition("browser.delete_report", "v1", BROWSER_SCHEMA),
            )
        )
        catalog = (
            AgentToolCatalogEntry(
                "browser.export_report", "v1", "Export an authorized report"
            ),
            AgentToolCatalogEntry(
                "browser.delete_report", "v1", "Delete an authorized report"
            ),
        )
        snapshot = build_tool_capability_snapshot(
            registry=registry,
            catalog=catalog,
            context=TrustedToolContext(
                tenant_id="tenant-a",
                user_id="user-1",
                role="publisher",
                job_id="J1",
                step_id="S1",
                granted_tool_ids=frozenset({"browser.export_report@v1"}),
            ),
        )

        translated = translate_snapshot_for_framework(snapshot)

        self.assertEqual(
            tuple(f"{tool.name}@{tool.version}" for tool in translated),
            ("browser.export_report@v1",),
        )
        self.assertTrue(
            all(
                tool.capability_snapshot_id == snapshot.snapshot_id
                for tool in translated
            )
        )


if __name__ == "__main__":
    unittest.main()
