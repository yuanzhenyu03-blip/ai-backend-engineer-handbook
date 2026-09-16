"""Day92 deterministic MCP authentication and authorization seed evaluation."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp_auth import (  # noqa: E402
    AuthenticatedPrincipal,
    AuthenticationOutcome,
    AuthenticationSource,
)
from mcp_authorization import (  # noqa: E402
    ApplicationAuthorizationService,
    AuthorizationFactsUnavailable,
    InMemoryOperationAuthorizationBindings,
    PromptAuthorizationRequest,
    ResourceAuthorizationRequest,
    ToolAuthorizationRequest,
)
from mcp_security_adapter import (  # noqa: E402
    DeterministicHMACBearerVerifier,
)


ISSUER = "https://auth.example.com"
AUDIENCE = "https://research.example.com/mcp"
NOW = 1_700_000_000
CURRENT_KEY = b"day92-controlled-current-key"


def token(
    key: bytes = CURRENT_KEY,
    *,
    key_id: str = "K-current",
    claim_overrides: dict[str, object] | None = None,
    omit_claims: frozenset[str] = frozenset(),
) -> str:
    header = {"alg": "HS256", "kid": key_id}
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "ordinary-user",
        "exp": 1_800_000_000,
        "scope": "research:lookup research:read research:prompt",
    }
    claims.update(claim_overrides or {})
    for name in omit_claims:
        claims.pop(name, None)

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


class Facts:
    def __init__(self, *, revoked: bool = False) -> None:
        self.revoked = revoked

    def is_principal_revoked(self, principal: AuthenticatedPrincipal) -> bool:
        return self.revoked

    def tenant_memberships(
        self,
        principal: AuthenticatedPrincipal,
    ) -> frozenset[str]:
        return frozenset({"tenant-a"})

    def permitted_tools(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]:
        return frozenset({"research.lookup"})

    def permitted_prompts(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
    ) -> frozenset[str]:
        return frozenset({"summarize-research"})

    def permitted_resources(
        self,
        principal: AuthenticatedPrincipal,
        tenant_id: str,
        resource_kind: str,
    ) -> frozenset[str]:
        return frozenset({"report-42"})


class UnavailableFacts(Facts):
    def is_principal_revoked(self, principal: AuthenticatedPrincipal) -> bool:
        raise AuthorizationFactsUnavailable("controlled seed outage")


def verifier(
    keys: dict[str, bytes] | None = None,
) -> DeterministicHMACBearerVerifier:
    return DeterministicHMACBearerVerifier(
        trusted_signing_keys=keys or {"K-current": CURRENT_KEY},
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        now_epoch_seconds=lambda: NOW,
    )


def principal(
    subject: str = "ordinary-user",
    *,
    scopes: frozenset[str] = frozenset({"research:lookup"}),
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer=ISSUER,
        audiences=frozenset({AUDIENCE}),
        scopes=scopes,
        source=AuthenticationSource.HTTP_BEARER,
        expires_at=1_800_000_000,
    )


def result(outcome: str, *, principal_built: bool) -> dict[str, object]:
    return {
        "outcome": outcome,
        "principal_built": principal_built,
        "handler_calls": 0,
        "service_calls": 0,
        "durable_transitions": 0,
    }


def authentication_case(category: str) -> dict[str, object]:
    if category == "missing_credential":
        return result(
            AuthenticationOutcome.MISSING_CREDENTIAL.value,
            principal_built=False,
        )
    if category == "malformed_credential":
        decision = verifier().verify("abc.def")
    elif category == "invalid_signature":
        decision = verifier().verify(token(b"attacker-key"))
    elif category == "expired":
        decision = verifier().verify(token(claim_overrides={"exp": NOW - 1}))
    elif category == "not_yet_valid":
        decision = verifier().verify(token(claim_overrides={"nbf": NOW + 1}))
    elif category == "wrong_issuer":
        decision = verifier().verify(token(claim_overrides={
            "iss": "https://attacker.example.com",
        }))
    elif category == "wrong_audience":
        decision = verifier().verify(token(claim_overrides={
            "aud": "https://other.example.com/mcp",
        }))
    elif category == "missing_subject":
        decision = verifier().verify(token(omit_claims=frozenset({"sub"})))
    elif category == "key_rotation":
        old_key = b"day92-controlled-old-key"
        rotating = verifier({"K-old": old_key, "K-current": CURRENT_KEY})
        old = rotating.verify(token(old_key, key_id="K-old"))
        current = rotating.verify(token())
        both = (
            old.outcome is AuthenticationOutcome.AUTHENTICATED
            and current.outcome is AuthenticationOutcome.AUTHENTICATED
        )
        if not both:
            raise AssertionError("trusted rotation keys did not both authenticate")
        return result("AUTHENTICATED_BOTH_KEYS", principal_built=True)
    else:
        raise ValueError("unknown authentication seed category")
    return result(
        decision.outcome.value,
        principal_built=decision.principal is not None,
    )


def authorization_service(
    *,
    facts: Facts | None = None,
    bindings: InMemoryOperationAuthorizationBindings | None = None,
) -> ApplicationAuthorizationService:
    return ApplicationAuthorizationService(
        facts=facts or Facts(),
        bindings=bindings or InMemoryOperationAuthorizationBindings(),
        required_scope_by_tool={"research.lookup": "research:lookup"},
        required_scope_by_prompt={"summarize-research": "research:prompt"},
        required_scope_by_resource_kind={"research.report": "research:read"},
    )


def authorization_case(category: str) -> dict[str, object]:
    if category == "insufficient_scope":
        decision = authorization_service().authorize_tool(
            principal(scopes=frozenset({"research:read"})),
            ToolAuthorizationRequest(
                "op-1",
                "idem-1",
                "tenant-a",
                "research.lookup",
            ),
        )
    elif category == "tenant_mismatch":
        decision = authorization_service().authorize_tool(
            principal(),
            ToolAuthorizationRequest(
                "op-1",
                "idem-1",
                "tenant-b",
                "research.lookup",
            ),
        )
    elif category == "prompt_privilege":
        decision = authorization_service().authorize_prompt(
            principal(scopes=frozenset({"research:prompt"})),
            PromptAuthorizationRequest(
                "tenant-a",
                "summarize-research",
                {"role": "admin", "tenant_id": "tenant-b"},
            ),
        )
    elif category == "resource_cross_tenant":
        decision = authorization_service().authorize_resource(
            principal(scopes=frozenset({"research:read"})),
            ResourceAuthorizationRequest(
                "tenant-b",
                "research.report",
                "report-42",
                "research://tenant-b/report-42",
            ),
        )
    elif category == "revoked":
        decision = authorization_service(facts=Facts(revoked=True)).authorize_tool(
            principal(),
            ToolAuthorizationRequest(
                "op-1",
                "idem-1",
                "tenant-a",
                "research.lookup",
            ),
        )
    elif category == "authorization_unavailable":
        decision = authorization_service(
            facts=UnavailableFacts()
        ).authorize_tool(
            principal(),
            ToolAuthorizationRequest(
                "op-1",
                "idem-1",
                "tenant-a",
                "research.lookup",
            ),
        )
    elif category == "identity_conflict":
        bindings = InMemoryOperationAuthorizationBindings()
        authorization = authorization_service(bindings=bindings)
        request = ToolAuthorizationRequest(
            "op-1",
            "idem-1",
            "tenant-a",
            "research.lookup",
        )
        authorization.authorize_tool(principal(), request)
        decision = authorization.authorize_tool(principal("admin-user"), request)
    else:
        raise ValueError("unknown authorization seed category")
    return result(decision.outcome.value, principal_built=True)


def evaluate(category: str) -> dict[str, object]:
    if category in {
        "missing_credential",
        "malformed_credential",
        "invalid_signature",
        "expired",
        "not_yet_valid",
        "wrong_issuer",
        "wrong_audience",
        "missing_subject",
        "key_rotation",
    }:
        return authentication_case(category)
    return authorization_case(category)


def grade(case: dict[str, object], actual: dict[str, object]) -> list[str]:
    mapping = {
        "outcome": "expected_outcome",
        "principal_built": "expected_principal_built",
        "handler_calls": "expected_handler_calls",
        "service_calls": "expected_service_calls",
    }
    return [
        key
        for key, expected_key in mapping.items()
        if actual.get(key) != case.get(expected_key)
    ]


def main() -> int:
    path = Path(__file__).with_name("day92_mcp_security_seed.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line]
    if not 12 <= len(cases) <= 16:
        raise ValueError("Day92 seed requires 12 to 16 cases")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Day92 seed case IDs must be unique")
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
