"""Day92 tests for transport authentication and credential minimization."""
import base64
import hashlib
import hmac
import json
import unittest
from dataclasses import asdict, fields

from mcp_auth import (
    AuthenticatedPrincipal,
    AuthenticationDecision,
    AuthenticationOutcome,
    AuthenticationSource,
)
from mcp_security_adapter import (
    AuthenticationGateOutcome,
    DeterministicHMACBearerVerifier,
    EdgeProtectionOutcome,
    HTTPPreAuthenticationGuard,
    MCPHTTPAuthenticationBoundary,
    MCPStdioAuthenticationBoundary,
)
from mcp_server import ServerToolRequest


class RecordingVerifier:
    def __init__(self, decision: AuthenticationDecision) -> None:
        self.decision = decision
        self.credentials: list[str] = []

    def verify(self, credential: str) -> AuthenticationDecision:
        self.credentials.append(credential)
        return self.decision


class RecordingAuthenticatedDispatch:
    def __init__(self) -> None:
        self.calls: list[tuple[AuthenticatedPrincipal, ServerToolRequest]] = []

    def dispatch(
        self,
        principal: AuthenticatedPrincipal,
        request: ServerToolRequest,
    ) -> None:
        self.calls.append((principal, request))


class FixedEdgeRateLimit:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.source_buckets: list[str] = []

    def allow(self, source_bucket: str) -> bool:
        self.source_buckets.append(source_bucket)
        return self.allowed


def principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject="ordinary-user",
        issuer="https://auth.example.com",
        audiences=frozenset({"https://research.example.com/mcp"}),
        scopes=frozenset({"research:lookup"}),
        source=AuthenticationSource.HTTP_BEARER,
        expires_at=1_800_000_000,
        client_id="research-client",
        token_id="token-7",
        signing_key_id="key-2026-09",
    )


def request() -> ServerToolRequest:
    return ServerToolRequest(
        protocol_request_id="day92-request-1",
        tool_name="research.lookup",
        arguments={
            "tenant_id": "tenant-a",
            "user_id": "admin-user",
            "query": "MCP security boundary",
        },
    )


def controlled_token(
    key_id: str,
    key: bytes,
    *,
    extra_header: dict[str, object] | None = None,
    claim_overrides: dict[str, object] | None = None,
    omit_claims: frozenset[str] = frozenset(),
) -> str:
    header: dict[str, object] = {"alg": "HS256", "kid": key_id}
    header.update(extra_header or {})
    claims = {
        "iss": "https://auth.example.com",
        "aud": "https://research.example.com/mcp",
        "sub": "ordinary-user",
        "exp": 1_800_000_000,
        "scope": "research:lookup research:read",
    }
    claims.update(claim_overrides or {})
    for claim_name in omit_claims:
        claims.pop(claim_name, None)

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


class Day92MCPAuthenticationTests(unittest.TestCase):
    def test_oversized_request_is_rejected_by_cheap_pre_auth_guard(self) -> None:
        rate_limit = FixedEdgeRateLimit(allowed=True)

        decision = HTTPPreAuthenticationGuard(
            maximum_body_bytes=1024,
            rate_limit=rate_limit,
        ).check(
            content_length=2048,
            source_bucket="controlled-source",
        )

        self.assertEqual(
            decision.outcome,
            EdgeProtectionOutcome.PAYLOAD_TOO_LARGE,
        )
        self.assertEqual(decision.http_status, 413)
        self.assertEqual(rate_limit.source_buckets, [])

    def test_coarse_edge_rate_limit_does_not_require_a_principal(self) -> None:
        rate_limit = FixedEdgeRateLimit(allowed=False)

        decision = HTTPPreAuthenticationGuard(
            maximum_body_bytes=1024,
            rate_limit=rate_limit,
        ).check(
            content_length=256,
            source_bucket="controlled-source",
        )

        self.assertEqual(
            decision.outcome,
            EdgeProtectionOutcome.RATE_LIMITED,
        )
        self.assertEqual(decision.http_status, 429)
        self.assertEqual(rate_limit.source_buckets, ["controlled-source"])

    def test_stdio_uses_trusted_launcher_not_request_identity_fields(self) -> None:
        launch_principal = AuthenticatedPrincipal(
            subject="local-research-worker",
            issuer="trusted-launcher://research-cli",
            audiences=frozenset({"local-mcp-server"}),
            scopes=frozenset({"research:lookup"}),
            source=AuthenticationSource.STDIO_TRUSTED_LAUNCH,
            expires_at=None,
            client_id="research-cli",
        )
        downstream = RecordingAuthenticatedDispatch()

        result = MCPStdioAuthenticationBoundary(
            launch_principal,
            downstream,
        ).handle_tool(request())

        self.assertEqual(
            result.outcome,
            AuthenticationGateOutcome.FORWARDED_TO_AUTHORIZATION,
        )
        self.assertEqual(result.authorization_dispatches, 1)
        self.assertEqual(len(downstream.calls), 1)
        forwarded_principal, forwarded_request = downstream.calls[0]
        self.assertEqual(forwarded_principal.subject, "local-research-worker")
        self.assertEqual(
            forwarded_principal.source,
            AuthenticationSource.STDIO_TRUSTED_LAUNCH,
        )
        self.assertEqual(forwarded_request.arguments["user_id"], "admin-user")
        self.assertIsNone(forwarded_principal.expires_at)

    def test_missing_credential_fails_before_verifier_and_authorization(self) -> None:
        verifier = RecordingVerifier(AuthenticationDecision.accepted(principal()))
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool(None, request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.MISSING_CREDENTIAL,
        )
        self.assertEqual(verifier.credentials, [])
        self.assertEqual(downstream.calls, [])
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)

    def test_malformed_credential_fails_before_verifier_and_authorization(self) -> None:
        verifier = RecordingVerifier(AuthenticationDecision.accepted(principal()))
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool("Basic client-secret", request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.MALFORMED_CREDENTIAL,
        )
        self.assertEqual(verifier.credentials, [])
        self.assertEqual(downstream.calls, [])

    def test_wrong_audience_never_builds_or_dispatches_a_principal(self) -> None:
        verifier = RecordingVerifier(AuthenticationDecision.rejected(
            AuthenticationOutcome.WRONG_AUDIENCE
        ))
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool("Bearer controlled-token", request())

        self.assertEqual(verifier.credentials, ["controlled-token"])
        self.assertIsNone(result.authentication.principal)
        self.assertEqual(downstream.calls, [])
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)

    def test_authenticated_request_forwards_only_sanitized_principal(self) -> None:
        verifier = RecordingVerifier(AuthenticationDecision.accepted(principal()))
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool("Bearer controlled-token", request())

        self.assertEqual(
            result.outcome,
            AuthenticationGateOutcome.FORWARDED_TO_AUTHORIZATION,
        )
        self.assertEqual(result.authorization_dispatches, 1)
        self.assertEqual(len(downstream.calls), 1)
        forwarded_principal, forwarded_request = downstream.calls[0]
        self.assertEqual(forwarded_principal.subject, "ordinary-user")
        self.assertEqual(forwarded_request.arguments["user_id"], "admin-user")

    def test_application_principal_has_no_raw_credential_field(self) -> None:
        field_names = {field.name for field in fields(AuthenticatedPrincipal)}
        serialized = asdict(principal())

        self.assertNotIn("raw_bearer_token", field_names)
        self.assertNotIn("access_token", field_names)
        self.assertNotIn("controlled-token", repr(serialized))

    def test_rotation_window_accepts_tokens_from_both_trusted_keys(self) -> None:
        old_key = b"controlled-old-key"
        new_key = b"controlled-new-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-old": old_key, "K-new": new_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )

        old_decision = verifier.verify(controlled_token("K-old", old_key))
        new_decision = verifier.verify(controlled_token("K-new", new_key))

        self.assertEqual(
            old_decision.outcome,
            AuthenticationOutcome.AUTHENTICATED,
        )
        self.assertEqual(
            new_decision.outcome,
            AuthenticationOutcome.AUTHENTICATED,
        )

    def test_removed_or_token_supplied_key_is_not_trusted(self) -> None:
        attacker_key = b"attacker-controlled-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-new": b"controlled-new-key"},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        token = controlled_token(
            "K-old",
            attacker_key,
            extra_header={"jwk": {"k": "attacker-controlled-key"}},
        )

        decision = verifier.verify(token)

        self.assertEqual(
            decision.outcome,
            AuthenticationOutcome.UNKNOWN_SIGNING_KEY,
        )
        self.assertIsNone(decision.principal)

    def test_removed_old_key_stops_before_authorization_and_handlers(self) -> None:
        old_key = b"controlled-old-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-new": b"controlled-new-key"},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool(
            f"Bearer {controlled_token('K-old', old_key)}",
            request(),
        )

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.UNKNOWN_SIGNING_KEY,
        )
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)
        self.assertEqual(downstream.calls, [])

    def test_client_id_cannot_replace_a_missing_subject(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        downstream = RecordingAuthenticatedDispatch()
        token = controlled_token(
            "K-current",
            signing_key,
            claim_overrides={"client_id": "nightly-research-job"},
            omit_claims=frozenset({"sub"}),
        )

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool(f"Bearer {token}", request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.MISSING_SUBJECT,
        )
        self.assertIsNone(result.authentication.principal)
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)
        self.assertEqual(downstream.calls, [])

    def test_not_before_in_the_future_stops_before_authorization(self) -> None:
        signing_key = b"controlled-current-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        downstream = RecordingAuthenticatedDispatch()
        token = controlled_token(
            "K-current",
            signing_key,
            claim_overrides={"nbf": 1_700_086_400},
        )

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool(f"Bearer {token}", request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.NOT_YET_VALID,
        )
        self.assertIsNone(result.authentication.principal)
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)
        self.assertEqual(downstream.calls, [])

    def test_invalid_signature_makes_all_payload_claims_untrusted(self) -> None:
        trusted_key = b"controlled-current-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": trusted_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        downstream = RecordingAuthenticatedDispatch()
        token = controlled_token(
            "K-current",
            b"attacker-signing-key",
            claim_overrides={
                "role": "admin",
                "tenant_id": "tenant-a",
            },
        )

        result = MCPHTTPAuthenticationBoundary(
            verifier,
            downstream,
        ).handle_tool(f"Bearer {token}", request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.INVALID_SIGNATURE,
        )
        self.assertIsNone(result.authentication.principal)
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)
        self.assertEqual(downstream.calls, [])

    def test_structurally_malformed_bearer_reaches_no_authorization(self) -> None:
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": b"controlled-current-key"},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        recording_verifier = RecordingVerifier(
            verifier.verify("abc.def")
        )
        downstream = RecordingAuthenticatedDispatch()

        result = MCPHTTPAuthenticationBoundary(
            recording_verifier,
            downstream,
        ).handle_tool("Bearer abc.def", request())

        self.assertEqual(result.outcome, AuthenticationGateOutcome.REJECTED)
        self.assertEqual(
            result.authentication.outcome,
            AuthenticationOutcome.MALFORMED_CREDENTIAL,
        )
        self.assertEqual(recording_verifier.credentials, ["abc.def"])
        self.assertIsNone(result.authentication.principal)
        self.assertEqual(result.authorization_dispatches, 0)
        self.assertEqual(result.handler_calls, 0)
        self.assertEqual(result.controlled_service_calls, 0)
        self.assertEqual(downstream.calls, [])

    def test_signed_tokens_still_enforce_issuer_audience_and_expiration(
        self,
    ) -> None:
        signing_key = b"controlled-current-key"
        verifier = DeterministicHMACBearerVerifier(
            trusted_signing_keys={"K-current": signing_key},
            expected_issuer="https://auth.example.com",
            expected_audience="https://research.example.com/mcp",
            now_epoch_seconds=lambda: 1_700_000_000,
        )
        cases = (
            (
                {"iss": "https://attacker.example.com"},
                AuthenticationOutcome.WRONG_ISSUER,
            ),
            (
                {"aud": "https://other.example.com/mcp"},
                AuthenticationOutcome.WRONG_AUDIENCE,
            ),
            (
                {"exp": 1_699_999_999},
                AuthenticationOutcome.EXPIRED,
            ),
        )

        for claim_overrides, expected_outcome in cases:
            with self.subTest(expected_outcome=expected_outcome):
                token = controlled_token(
                    "K-current",
                    signing_key,
                    claim_overrides=claim_overrides,
                )

                decision = verifier.verify(token)

                self.assertEqual(decision.outcome, expected_outcome)
                self.assertIsNone(decision.principal)


if __name__ == "__main__":
    unittest.main()
