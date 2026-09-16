"""Day92 composition tests across authentication, authorization and Day91."""
import base64
import hashlib
import hmac
import json
import unittest

from mcp_auth import AuthenticatedPrincipal, AuthenticationDecision
from mcp_authorization import (
    ApplicationAuthorizationService,
    AuthorizationDecision,
    AuthorizationFactsUnavailable,
    AuthorizationOutcome,
    InMemoryOperationAuthorizationBindings,
    ToolAuthorizationPermit,
    ToolAuthorizationRequest,
)
from mcp_security_adapter import (
    DeterministicHMACBearerVerifier,
    MCPToolSecurityBoundary,
    ToolSecurityOutcome,
    TrustedToolOperationContext,
    security_http_status,
)
from mcp_server import (
    MCPServerRequestCoordinator,
    ServerToolDecision,
    ServerToolOutcome,
    ServerToolRequest,
)
from mcp_server_handlers import (
    ApplicationAdmissionDecision,
    ApplicationAdmissionOutcome,
    ApplicationOutputValidationDecision,
    ApplicationOutputValidationOutcome,
    ApplicationToolPermit,
    InMemoryOperationRegistry,
    OperationInvocationStatus,
    ResearchLookupHandler,
)


def controlled_token(
    key: bytes,
    *,
    scope: str = "research:lookup",
    extra_claims: dict[str, object] | None = None,
) -> str:
    header = {"alg": "HS256", "kid": "K-current"}
    claims = {
        "iss": "https://auth.example.com",
        "aud": "https://research.example.com/mcp",
        "sub": "ordinary-user",
        "exp": 1_800_000_000,
        "scope": scope,
    }
    claims.update(extra_claims or {})

    def encode(value: object) -> str:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = hmac.new(
        key,
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{signing_input}.{encoded_signature.decode('ascii')}"


class CurrentFacts:
    def is_principal_revoked(self, principal: AuthenticatedPrincipal) -> bool:
        return False

    def tenant_memberships(
        self,
        principal: AuthenticatedPrincipal,
    ) -> frozenset[str]:
        if principal.subject == "ordinary-user":
            return frozenset({"tenant-a"})
        return frozenset()

    def permitted_tools(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]:
        if principal.subject == "ordinary-user" and tenant_id == "tenant-a":
            return frozenset({"research.lookup"})
        return frozenset()

    def permitted_prompts(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]:
        return frozenset()

    def permitted_resources(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
        resource_kind: str,
    ) -> frozenset[str]:
        return frozenset()


class UnavailableFacts(CurrentFacts):
    def is_principal_revoked(self, principal: AuthenticatedPrincipal) -> bool:
        raise AuthorizationFactsUnavailable("controlled authorization outage")


class RecordingVerifier:
    def __init__(self, delegate: DeterministicHMACBearerVerifier) -> None:
        self.delegate = delegate
        self.calls = 0

    def verify(self, credential: str) -> AuthenticationDecision:
        self.calls += 1
        return self.delegate.verify(credential)


class RecordingAuthorization:
    def __init__(self, delegate: ApplicationAuthorizationService) -> None:
        self.delegate = delegate
        self.calls: list[tuple[AuthenticatedPrincipal, ToolAuthorizationRequest]] = []

    def authorize_tool(
        self,
        principal: AuthenticatedPrincipal,
        request: ToolAuthorizationRequest,
    ) -> AuthorizationDecision:
        self.calls.append((principal, request))
        return self.delegate.authorize_tool(principal, request)


class PermitAdmission:
    def __init__(self, permit: ToolAuthorizationPermit) -> None:
        self.permit = permit

    def admit(self, request: ServerToolRequest) -> ApplicationAdmissionDecision:
        if request.tool_name != self.permit.tool_name:
            return ApplicationAdmissionDecision(
                outcome=ApplicationAdmissionOutcome.REJECTED,
                safe_reason="authorized Tool does not match the request",
            )
        return ApplicationAdmissionDecision(
            outcome=ApplicationAdmissionOutcome.ADMITTED,
            safe_reason="Day92 authorization permit admitted",
            permit=ApplicationToolPermit(
                application_operation_id=self.permit.application_operation_id,
                tenant_id=self.permit.tenant_id,
                idempotency_key=self.permit.idempotency_key,
            ),
        )


class RecordingLookupService:
    def __init__(self, *, fail_after_possible_execution: bool = False) -> None:
        self.calls: list[tuple[str, ApplicationToolPermit]] = []
        self.fail_after_possible_execution = fail_after_possible_execution

    def lookup(
        self,
        query: str,
        permit: ApplicationToolPermit,
    ) -> dict[str, object]:
        self.calls.append((query, permit))
        if self.fail_after_possible_execution:
            raise TimeoutError("controlled timeout after possible execution")
        return {
            "query": query,
            "application_operation_id": permit.application_operation_id,
            "tenant_id": permit.tenant_id,
        }


class AdmitOutput:
    def validate(
        self,
        candidate: dict[str, object],
        permit: ApplicationToolPermit,
    ) -> ApplicationOutputValidationDecision:
        return ApplicationOutputValidationDecision(
            outcome=ApplicationOutputValidationOutcome.ADMITTED,
            safe_reason="controlled candidate is valid",
        )


class Lease:
    def __init__(self) -> None:
        self.releases = 0

    def release(self) -> None:
        self.releases += 1


class Capacity:
    def __init__(self, *, available: bool = True) -> None:
        self.lease = Lease()
        self.calls = 0
        self.available = available

    def try_acquire(self) -> Lease | None:
        self.calls += 1
        return self.lease if self.available else None


class Day91Execution:
    def __init__(
        self,
        service: RecordingLookupService,
        *,
        capacity_available: bool = True,
    ) -> None:
        self.service = service
        self.capacity = Capacity(available=capacity_available)
        self.registry = InMemoryOperationRegistry()

    def execute(
        self,
        request: ServerToolRequest,
        permit: ToolAuthorizationPermit,
    ) -> ServerToolDecision:
        handler = ResearchLookupHandler(
            admission=PermitAdmission(permit),
            service=self.service,
            idempotency=self.registry,
            output_validation=AdmitOutput(),
        )
        return MCPServerRequestCoordinator(
            self.capacity,
            handler,
        ).handle_tool(request)


class Day92MCPSecurityIntegrationTests(unittest.TestCase):
    def test_positive_path_calls_each_boundary_once_without_committing(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )
        request = ServerToolRequest(
            protocol_request_id="day92-positive-1",
            tool_name="research.lookup",
            arguments={
                "query": "MCP security boundary",
                "tenant_id": "tenant-b",
                "user_id": "admin-user",
            },
        )

        decision = boundary.handle_tool(
            f"Bearer {controlled_token(signing_key)}",
            TrustedToolOperationContext(
                application_operation_id="op-report-42",
                idempotency_key="idem-report-42",
                requested_tenant_id="tenant-a",
            ),
            request,
        )

        self.assertEqual(decision.outcome, ToolSecurityOutcome.SERVER_DECIDED)
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(len(authorization.calls), 1)
        self.assertEqual(decision.authentication_calls, 1)
        self.assertEqual(decision.authorization_calls, 1)
        self.assertEqual(decision.handler_calls, 1)
        self.assertEqual(decision.controlled_service_calls, 1)
        self.assertEqual(decision.durable_transitions, 0)
        self.assertEqual(execution.capacity.calls, 1)
        self.assertEqual(execution.capacity.lease.releases, 1)
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(service.calls[0][1].tenant_id, "tenant-a")

    def test_capacity_rejection_occurs_after_security_before_handler(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service, capacity_available=False)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )

        decision = boundary.handle_tool(
            f"Bearer {controlled_token(signing_key)}",
            TrustedToolOperationContext(
                application_operation_id="op-capacity-1",
                idempotency_key="idem-capacity-1",
                requested_tenant_id="tenant-a",
            ),
            ServerToolRequest(
                protocol_request_id="day92-capacity-1",
                tool_name="research.lookup",
                arguments={"query": "capacity boundary"},
            ),
        )

        self.assertEqual(decision.outcome, ToolSecurityOutcome.SERVER_DECIDED)
        assert decision.server is not None
        self.assertEqual(
            decision.server.outcome,
            ServerToolOutcome.BACKPRESSURE_REJECTED,
        )
        self.assertEqual(decision.authentication_calls, 1)
        self.assertEqual(decision.authorization_calls, 1)
        self.assertEqual(execution.capacity.calls, 1)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(decision.durable_transitions, 0)
        self.assertEqual(service.calls, [])
        self.assertEqual(execution.capacity.lease.releases, 0)

    def test_signed_admin_role_cannot_replace_scope_or_tool_grant(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )
        signed_admin_token = controlled_token(
            signing_key,
            scope="research:read",
            extra_claims={"role": "admin"},
        )

        decision = boundary.handle_tool(
            f"Bearer {signed_admin_token}",
            TrustedToolOperationContext(
                application_operation_id="op-signed-role-1",
                idempotency_key="idem-signed-role-1",
                requested_tenant_id="tenant-a",
            ),
            ServerToolRequest(
                protocol_request_id="day92-signed-role-1",
                tool_name="research.lookup",
                arguments={"query": "signed claim boundary"},
            ),
        )

        self.assertEqual(
            decision.outcome,
            ToolSecurityOutcome.AUTHORIZATION_REJECTED,
        )
        assert decision.authentication.principal is not None
        self.assertFalse(hasattr(decision.authentication.principal, "role"))
        assert decision.authorization is not None
        self.assertEqual(
            decision.authorization.outcome,
            AuthorizationOutcome.INSUFFICIENT_SCOPE,
        )
        self.assertEqual(security_http_status(decision), 403)
        self.assertEqual(decision.authentication_calls, 1)
        self.assertEqual(decision.authorization_calls, 1)
        self.assertEqual(execution.capacity.calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(service.calls, [])

    def test_malformed_token_maps_to_401_before_authorization(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service)

        decision = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        ).handle_tool(
            "Bearer abc.def",
            TrustedToolOperationContext(
                application_operation_id="op-malformed-1",
                idempotency_key="idem-malformed-1",
                requested_tenant_id="tenant-a",
            ),
            ServerToolRequest(
                protocol_request_id="day92-malformed-1",
                tool_name="research.lookup",
                arguments={"query": "malformed credential"},
            ),
        )

        self.assertEqual(
            decision.outcome,
            ToolSecurityOutcome.AUTHENTICATION_REJECTED,
        )
        self.assertEqual(security_http_status(decision), 401)
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(authorization.calls, [])
        self.assertEqual(execution.capacity.calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(service.calls, [])

    def test_authorization_dependency_outage_maps_to_503_fail_closed(self) -> None:
        signing_key = b"controlled-current-key"
        bindings = InMemoryOperationAuthorizationBindings()
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=UnavailableFacts(),
            bindings=bindings,
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )
        operation = TrustedToolOperationContext(
            application_operation_id="op-auth-outage-1",
            idempotency_key="idem-auth-outage-1",
            requested_tenant_id="tenant-a",
        )
        request = ServerToolRequest(
            protocol_request_id="day92-auth-outage-1",
            tool_name="research.lookup",
            arguments={"query": "authorization outage"},
        )

        decision = boundary.handle_tool(
            f"Bearer {controlled_token(signing_key)}",
            operation,
            request,
        )

        self.assertEqual(
            decision.outcome,
            ToolSecurityOutcome.AUTHORIZATION_REJECTED,
        )
        assert decision.authorization is not None
        self.assertEqual(
            decision.authorization.outcome,
            AuthorizationOutcome.AUTHORIZATION_UNAVAILABLE,
        )
        self.assertEqual(security_http_status(decision), 503)
        self.assertEqual(decision.authentication_calls, 1)
        self.assertEqual(decision.authorization_calls, 1)
        self.assertEqual(execution.capacity.calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(service.calls, [])

        authorization.delegate = ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=bindings,
            required_scope_by_tool={"research.lookup": "research:lookup"},
        )
        recovered = boundary.handle_tool(
            f"Bearer {controlled_token(signing_key)}",
            operation,
            ServerToolRequest(
                protocol_request_id="day92-auth-outage-retry-1",
                tool_name=request.tool_name,
                arguments=request.arguments,
            ),
        )

        self.assertEqual(recovered.outcome, ToolSecurityOutcome.SERVER_DECIDED)
        self.assertIsNone(security_http_status(recovered))
        self.assertEqual(verifier.calls, 2)
        self.assertEqual(len(authorization.calls), 2)
        self.assertEqual(execution.capacity.calls, 1)
        self.assertEqual(recovered.handler_calls, 1)
        self.assertEqual(recovered.controlled_service_calls, 1)
        self.assertEqual(len(service.calls), 1)

    def test_machine_principal_cannot_inherit_human_tenant_membership(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService()
        execution = Day91Execution(service)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )
        machine_token = controlled_token(
            signing_key,
            extra_claims={
                "sub": "research-worker",
                "client_id": "nightly-research-job",
            },
        )

        decision = boundary.handle_tool(
            f"Bearer {machine_token}",
            TrustedToolOperationContext(
                application_operation_id="op-machine-1",
                idempotency_key="idem-machine-1",
                requested_tenant_id="tenant-a",
            ),
            ServerToolRequest(
                protocol_request_id="day92-machine-1",
                tool_name="research.lookup",
                arguments={"query": "machine identity boundary"},
            ),
        )

        self.assertEqual(
            decision.outcome,
            ToolSecurityOutcome.AUTHORIZATION_REJECTED,
        )
        assert decision.authentication.principal is not None
        self.assertEqual(
            decision.authentication.principal.subject,
            "research-worker",
        )
        self.assertEqual(
            decision.authentication.principal.client_id,
            "nightly-research-job",
        )
        assert decision.authorization is not None
        self.assertEqual(
            decision.authorization.outcome,
            AuthorizationOutcome.TENANT_MEMBERSHIP_MISMATCH,
        )
        self.assertEqual(execution.capacity.calls, 0)
        self.assertEqual(decision.handler_calls, 0)
        self.assertEqual(decision.controlled_service_calls, 0)
        self.assertEqual(service.calls, [])

    def test_timeout_after_possible_execution_requires_reconciliation(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = RecordingVerifier(DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        ))
        authorization = RecordingAuthorization(ApplicationAuthorizationService(
            facts=CurrentFacts(),
            bindings=InMemoryOperationAuthorizationBindings(),
            required_scope_by_tool={"research.lookup": "research:lookup"},
        ))
        service = RecordingLookupService(fail_after_possible_execution=True)
        execution = Day91Execution(service)
        boundary = MCPToolSecurityBoundary(
            verifier,
            authorization,
            execution,
        )

        with self.assertRaisesRegex(
            TimeoutError,
            "timeout after possible execution",
        ):
            boundary.handle_tool(
                f"Bearer {controlled_token(signing_key)}",
                TrustedToolOperationContext(
                    application_operation_id="op-timeout-1",
                    idempotency_key="idem-timeout-1",
                    requested_tenant_id="tenant-a",
                ),
                ServerToolRequest(
                    protocol_request_id="day92-timeout-1",
                    tool_name="research.lookup",
                    arguments={"query": "unknown outcome"},
                ),
            )

        self.assertEqual(verifier.calls, 1)
        self.assertEqual(len(authorization.calls), 1)
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(
            execution.registry.status("op-timeout-1"),
            OperationInvocationStatus.PENDING_RECONCILIATION,
        )
        self.assertEqual(execution.capacity.lease.releases, 1)

        duplicate = boundary.handle_tool(
            f"Bearer {controlled_token(signing_key)}",
            TrustedToolOperationContext(
                application_operation_id="op-timeout-1",
                idempotency_key="idem-timeout-1",
                requested_tenant_id="tenant-a",
            ),
            ServerToolRequest(
                protocol_request_id="day92-timeout-retry-1",
                tool_name="research.lookup",
                arguments={"query": "unknown outcome"},
            ),
        )

        self.assertEqual(
            duplicate.outcome,
            ToolSecurityOutcome.AUTHORIZATION_REJECTED,
        )
        assert duplicate.authorization is not None
        self.assertEqual(
            duplicate.authorization.outcome,
            AuthorizationOutcome.DUPLICATE,
        )
        self.assertEqual(duplicate.handler_calls, 0)
        self.assertEqual(duplicate.controlled_service_calls, 0)
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(execution.capacity.calls, 1)


if __name__ == "__main__":
    unittest.main()
