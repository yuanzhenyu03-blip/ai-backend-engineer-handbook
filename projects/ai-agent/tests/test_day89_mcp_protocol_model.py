"""Day89 focused tests for the bounded, SDK-independent MCP model."""
import unittest

from agent_framework_adapter import (
    Committer,
    CurrentFacts,
    FrameworkToolCall,
    ProposalEnvelope,
    ToolProposal,
    canonical_intent_hash,
)
from mcp_fake_transport import FakeMCPTransport
from mcp_protocol_model import (
    BindingStatus,
    ComplianceOutcome,
    ExternalContentCandidate,
    ExternalContentKind,
    CURRENT_SPECIFICATION_VERSION,
    MCPProtocolBoundary,
    MCPRequestDTO,
    MCPResponseDTO,
    ProtocolOutcome,
    OutputValidationOutcome,
    ReconciledOperationStatus,
    ReconciliationEvidence,
    ReconciliationOutcome,
    validate_reconciliation_evidence,
    propose_fact_repair,
    validate_external_content_candidate,
)
from pydantic_ai_framework_adapter import PydanticAIAdapter


def tool_request(
    request_id: str = "mcp-request-1",
    *,
    observed_server_capabilities: frozenset[str] = frozenset({"tools"}),
) -> MCPRequestDTO:
    return MCPRequestDTO(
        CURRENT_SPECIFICATION_VERSION,
        request_id,
        "tools/call",
        {"name": "search_documents", "arguments": {"query": "MCP"}},
        observed_server_capabilities=observed_server_capabilities,
    )


class Day89MCPProtocolModelTests(unittest.TestCase):
    def test_valid_request_becomes_protocol_observation_only(self) -> None:
        response = MCPResponseDTO(
            "mcp-request-1",
            result={"resultType": "complete", "documents": []},
        )
        transport = FakeMCPTransport(responses={"mcp-request-1": response})
        boundary = MCPProtocolBoundary(transport)

        observation = boundary.dispatch(
            tool_request(), application_operation_id="op-search-42"
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.PROTOCOL_RESULT)
        self.assertEqual(observation.application_operation_id, "op-search-42")
        self.assertFalse(observation.durable_transition)
        self.assertEqual(len(transport.sent), 1)

    def test_mcp_capability_cannot_bypass_day88_committer(self) -> None:
        transport = FakeMCPTransport()
        protocol_boundary = MCPProtocolBoundary(transport)

        class MCPBackedFakeTool:
            def invoke(
                self,
                *,
                operation_id: str,
                proposal: ToolProposal,
            ) -> dict[str, object]:
                observation = protocol_boundary.dispatch(
                    MCPRequestDTO(
                        CURRENT_SPECIFICATION_VERSION,
                        "mcp-request-governed",
                        "tools/call",
                        {
                            "name": proposal.tool_name,
                            "arguments": {
                                "amount_minor": proposal.amount_minor,
                                "currency": proposal.currency,
                            },
                        },
                        observed_server_capabilities=frozenset({"tools"}),
                    ),
                    application_operation_id=operation_id,
                )
                return {
                    "protocol_outcome": observation.outcome.value,
                    "durable_transition": observation.durable_transition,
                }

        proposal = ToolProposal("refund", 100, "USD")
        envelope = ProposalEnvelope(
            "op-governed",
            "attempt-1",
            "approval-governed",
            5,
            9,
            2_000,
        )
        revoked_facts = CurrentFacts(
            "op-governed",
            False,
            "approval-governed",
            canonical_intent_hash(proposal),
            5,
            9,
            1_000,
        )

        audit = Committer(MCPBackedFakeTool()).process(
            PydanticAIAdapter(),
            FrameworkToolCall(
                "proposal_handler",
                {
                    "tool_name": "refund",
                    "amount_minor": 100,
                    "currency": "USD",
                },
            ),
            envelope,
            revoked_facts,
        )

        self.assertEqual(audit.reasons, ("grant_revoked",))
        self.assertFalse(audit.tool_called)
        self.assertEqual(protocol_boundary.bindings, {})
        self.assertEqual(transport.sent, [])

    def test_unsupported_version_fails_before_binding_or_send(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        request = MCPRequestDTO(
            "2025-11-25",
            "mcp-request-old",
            "tools/call",
            {"name": "search_documents", "arguments": {}},
        )

        observation = boundary.dispatch(
            request, application_operation_id="op-search-42"
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.UNSUPPORTED_VERSION)
        self.assertEqual(boundary.bindings, {})
        self.assertEqual(transport.sent, [])

    def test_unknown_method_fails_closed(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        request = MCPRequestDTO(
            CURRENT_SPECIFICATION_VERSION,
            "mcp-request-2",
            "operations/commit",
            {},
        )

        observation = boundary.dispatch(request, application_operation_id="op-2")

        self.assertEqual(observation.outcome, ProtocolOutcome.UNKNOWN_METHOD)
        self.assertEqual(transport.sent, [])

    def test_invalid_params_fail_closed(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        request = MCPRequestDTO(
            CURRENT_SPECIFICATION_VERSION,
            "mcp-request-3",
            "tools/call",
            {"name": "search_documents", "arguments": {}, "approve": True},
        )

        observation = boundary.dispatch(request, application_operation_id="op-3")

        self.assertEqual(observation.outcome, ProtocolOutcome.INVALID_MESSAGE)
        self.assertEqual(transport.sent, [])

    def test_missing_server_capability_fails_before_send(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)

        observation = boundary.dispatch(
            tool_request(observed_server_capabilities=frozenset()),
            application_operation_id="op-search-42",
        )

        self.assertEqual(
            observation.outcome, ProtocolOutcome.CAPABILITY_REJECTED
        )
        self.assertEqual(transport.sent, [])

    def test_capability_evidence_is_not_reused_across_requests(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        first = boundary.dispatch(
            tool_request("mcp-request-1"),
            application_operation_id="op-search-1",
        )

        second = boundary.dispatch(
            tool_request(
                "mcp-request-2",
                observed_server_capabilities=frozenset(),
            ),
            application_operation_id="op-search-2",
        )

        self.assertEqual(first.outcome, ProtocolOutcome.PENDING_RECONCILIATION)
        self.assertEqual(second.outcome, ProtocolOutcome.CAPABILITY_REJECTED)
        self.assertNotIn("mcp-request-2", boundary.bindings)
        self.assertEqual(
            [request.protocol_request_id for request in transport.sent],
            ["mcp-request-1"],
        )

    def test_request_id_and_operation_id_are_stored_separately(self) -> None:
        transport = FakeMCPTransport(responses={"mcp-request-1": None})
        boundary = MCPProtocolBoundary(transport)

        boundary.dispatch(tool_request(), application_operation_id="op-search-42")

        binding = boundary.bindings["mcp-request-1"]
        self.assertEqual(binding.protocol_request_id, "mcp-request-1")
        self.assertEqual(binding.application_operation_id, "op-search-42")

    def test_unknown_response_id_has_no_business_effect(self) -> None:
        boundary = MCPProtocolBoundary(FakeMCPTransport())

        observation = boundary.correlate(
            MCPResponseDTO(
                "mcp-request-999",
                result={"resultType": "complete", "documents": []},
            )
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.UNKNOWN_RESPONSE)
        self.assertIsNone(observation.application_operation_id)
        self.assertFalse(observation.durable_transition)

    def test_duplicate_response_does_not_repeat_transition(self) -> None:
        response = MCPResponseDTO(
            "mcp-request-1",
            result={"resultType": "complete", "documents": []},
        )
        transport = FakeMCPTransport(responses={"mcp-request-1": response})
        boundary = MCPProtocolBoundary(transport)
        boundary.dispatch(tool_request(), application_operation_id="op-search-42")

        duplicate = boundary.correlate(response)

        self.assertEqual(duplicate.outcome, ProtocolOutcome.DUPLICATE)
        self.assertFalse(duplicate.durable_transition)

    def test_conflicting_response_fails_closed(self) -> None:
        first = MCPResponseDTO(
            "mcp-request-1",
            result={"resultType": "complete", "published": True},
        )
        transport = FakeMCPTransport(responses={"mcp-request-1": first})
        boundary = MCPProtocolBoundary(transport)
        boundary.dispatch(tool_request(), application_operation_id="op-publish-42")

        conflict = boundary.correlate(
            MCPResponseDTO(
                "mcp-request-1",
                result={"resultType": "complete", "published": False},
            )
        )

        self.assertEqual(conflict.outcome, ProtocolOutcome.CONFLICT)
        self.assertEqual(
            boundary.binding_status["mcp-request-1"], BindingStatus.CONFLICT
        )
        self.assertFalse(conflict.durable_transition)

    def test_peer_operation_id_cannot_override_local_binding(self) -> None:
        response = MCPResponseDTO(
            "mcp-request-1",
            result={
                "resultType": "complete",
                "application_operation_id": "op-tenant-b-report-99",
            },
        )
        transport = FakeMCPTransport(responses={"mcp-request-1": response})
        boundary = MCPProtocolBoundary(transport)

        observation = boundary.dispatch(
            tool_request(), application_operation_id="op-tenant-a-report-42"
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.CONFLICT)
        self.assertEqual(
            observation.application_operation_id, "op-tenant-a-report-42"
        )

    def test_timeout_before_send_removes_binding(self) -> None:
        transport = FakeMCPTransport(
            timeout_before_send=frozenset({"mcp-request-1"})
        )
        boundary = MCPProtocolBoundary(transport)

        observation = boundary.dispatch(
            tool_request(), application_operation_id="op-search-42"
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.PROTOCOL_ERROR)
        self.assertEqual(boundary.bindings, {})
        self.assertEqual(transport.sent, [])

    def test_timeout_after_possible_send_preserves_binding_for_reconciliation(self) -> None:
        transport = FakeMCPTransport(
            timeout_after_possible_send=frozenset({"mcp-request-1"})
        )
        boundary = MCPProtocolBoundary(transport)

        observation = boundary.dispatch(
            tool_request(), application_operation_id="op-publish-42"
        )

        self.assertEqual(observation.outcome, ProtocolOutcome.OUTCOME_UNKNOWN)
        self.assertEqual(len(transport.sent), 1)
        self.assertEqual(
            boundary.binding_status["mcp-request-1"],
            BindingStatus.PENDING_RECONCILIATION,
        )
        self.assertEqual(
            boundary.bindings["mcp-request-1"].application_operation_id,
            "op-publish-42",
        )
        self.assertFalse(observation.durable_transition)

    def test_cross_tenant_reconciliation_conflict_has_no_side_effects(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        external_tool_calls: list[str] = []
        boundary.dispatch(
            tool_request(),
            application_operation_id="op-report-42",
            tenant_id="tenant-a",
            resource_id="research-report-42",
            idempotency_key="idem-report-42",
        )
        transport.sent.clear()  # Measure reconciliation, not original dispatch.

        decision = validate_reconciliation_evidence(
            boundary.bindings["mcp-request-1"],
            ReconciliationEvidence(
                application_operation_id="op-report-42",
                tenant_id="tenant-b",
                resource_id="research-report-42",
                idempotency_key="idem-report-42",
                external_object_id="external-report-77",
            ),
        )

        self.assertEqual(
            decision.outcome,
            ReconciliationOutcome.RECONCILIATION_CONFLICT,
        )
        self.assertFalse(decision.durable_transition)
        self.assertEqual(transport.sent, [])
        self.assertEqual(external_tool_calls, [])
        self.assertEqual(
            boundary.binding_status["mcp-request-1"],
            BindingStatus.PENDING_RECONCILIATION,
        )

    def test_fact_repair_records_success_and_authorization_violation_separately(self) -> None:
        transport = FakeMCPTransport()
        boundary = MCPProtocolBoundary(transport)
        boundary.dispatch(
            tool_request(),
            application_operation_id="op-report-42",
            tenant_id="tenant-a",
            resource_id="research-report-42",
            idempotency_key="idem-report-42",
        )
        transport.sent.clear()
        decision = validate_reconciliation_evidence(
            boundary.bindings["mcp-request-1"],
            ReconciliationEvidence(
                application_operation_id="op-report-42",
                tenant_id="tenant-a",
                resource_id="research-report-42",
                idempotency_key="idem-report-42",
                external_object_id="external-report-77",
            ),
        )

        proposal = propose_fact_repair(
            decision,
            authorization_valid_at_effect=False,
        )

        self.assertEqual(
            proposal.operation_status, ReconciledOperationStatus.SUCCEEDED
        )
        self.assertEqual(
            proposal.compliance_outcome,
            ComplianceOutcome.AUTHORIZATION_VIOLATION,
        )
        self.assertEqual(proposal.external_tool_calls, 0)
        self.assertFalse(proposal.durable_transition)
        self.assertEqual(transport.sent, [])

    def test_cross_tenant_resource_is_rejected_before_read(self) -> None:
        boundary = MCPProtocolBoundary(FakeMCPTransport())
        boundary.dispatch(
            tool_request(),
            application_operation_id="op-report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )

        decision = validate_external_content_candidate(
            boundary.bindings["mcp-request-1"],
            ExternalContentCandidate(
                ExternalContentKind.RESOURCE,
                "research://tenant-b/report-42",
                tenant_id="tenant-b",
                resource_id="report-42",
            ),
        )

        self.assertEqual(
            decision.outcome,
            OutputValidationOutcome.RESOURCE_SCOPE_REJECTED,
        )
        self.assertEqual(decision.resource_reads, 0)
        self.assertFalse(decision.durable_transition)

    def test_server_prompt_cannot_mutate_application_policy(self) -> None:
        binding = MCPProtocolBoundary(FakeMCPTransport())
        binding.dispatch(
            tool_request(),
            application_operation_id="op-report-42",
            tenant_id="tenant-a",
            resource_id="report-42",
        )

        decision = validate_external_content_candidate(
            binding.bindings["mcp-request-1"],
            ExternalContentCandidate(
                ExternalContentKind.PROMPT,
                "prompt://server/ignore-authorization",
                injection_suspected=True,
            ),
        )

        self.assertEqual(
            decision.outcome,
            OutputValidationOutcome.INDIRECT_PROMPT_INJECTION,
        )
        self.assertEqual(decision.policy_mutations, 0)
        self.assertFalse(decision.durable_transition)


if __name__ == "__main__":
    unittest.main()
