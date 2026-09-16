# Day92 — MCP Authentication, Authorization and Tenant Isolation

> Classroom baseline: `dc20c2192945e075d37c8c4d9de3363dd3dbcf6b`
> MCP specification/schema observed during class: `2026-07-28`
> SDK integration pin inherited from Day91: `mcp==2.2.0`
> Production readiness: `MORE_EVIDENCE_NEEDED`

## Decision

MCP transport data does not establish application identity or authority. The HTTP adapter extracts and
verifies a Bearer credential, then passes only a minimized `AuthenticatedPrincipal` to application code.
The stdio adapter receives identity from a trusted Launcher/process context and does not reinterpret request
arguments as credentials.

Application authorization checks current revocation, required scope, tenant membership and the exact Tool,
Resource or Prompt grant. Successful checks issue a narrow permit bound to the verified principal and target.
Day91 handlers remain behind this boundary and still cannot access a durable business Committer.

## Total boundary

```text
cheap edge size/source limits
→ transport-specific authentication
→ minimized authenticated principal
→ current application authorization facts
→ exact principal/tenant/capability permit
→ application capacity admission
→ Day91 handler
→ controlled service
→ candidate result
→ Day90 correlation and output validation
→ Committer
```

## HTTP versus stdio

| Transport | Trusted identity source | Rejected identity sources |
| --- | --- | --- |
| HTTP | per-request verified Bearer token | request payload user/role/tenant; token-supplied key |
| stdio | trusted Launcher and process context | command arguments or MCP payload pretending to be identity |

An HTTP principal requires a positive expiration. A stdio principal may have no token expiration because its
authentication lifetime is the trusted process channel, but every operation still checks current revocation,
membership and grants.

## Token validation

The deterministic classroom verifier enforces:

- trusted signing key selected by `kid`, with no request-supplied key trust;
- exact issuer and required audience;
- expiration and optional not-before time;
- non-empty subject;
- minimized OAuth scope and optional client metadata;
- overlap windows in which old and new trusted rotation keys both validate.

Missing/malformed credentials, bad signatures, unknown keys, expired/not-yet-valid tokens, wrong issuer or
audience and missing subject fail before authorization. No raw token enters the principal or handler.

The verifier uses deterministic HMAC only to make local negative paths executable. Production must use the
trusted issuer's standard JWT/JWKS implementation, cache policy, rotation rules and operational controls.

## Authorization and tenant isolation

Authentication proves an identity claim. Authorization decides whether that exact identity may perform one
operation. A signed role claim, client capability, URI, Prompt argument or payload tenant cannot replace:

```text
required scope
AND current non-revoked principal
AND current tenant membership
AND exact Tool/Resource/Prompt grant
```

Resource and Prompt permits deliberately omit executable authority they do not need. A Resource URI is a
requested target, not membership evidence. A Prompt permit authorizes rendering only and cannot invoke a Tool
or Resource. Cross-tenant and nonexistent Resources share a safe external message to resist enumeration.

## Identity, retry and unknown outcomes

An application operation is bound to issuer, subject, operation ID, idempotency key, tenant and Tool. The same
binding is a duplicate; a different binding for the same operation is an identity conflict. Neither path calls
the controlled service again.

Retry is evidence-driven:

| Evidence | Action |
| --- | --- |
| authentication/authorization/capacity rejected before handler | reuse original operation identity after correction or recovery |
| service may have executed before timeout | mark `PENDING_RECONCILIATION`; do not blindly retry |

HTTP status mapping is limited to HTTP security failures: invalid identity is 401, explicit authorization
denial is 403 and unavailable authorization infrastructure is 503. Later MCP and business outcomes remain
owned by their protocol/application layers.

## DoS and capacity order

Identity-independent maximum body size and source-bucket rate limits may run before authentication. They must
not use payload tenant identity. Principal/tenant quotas and application capacity admission run only after
authentication and authorization. MCP capability negotiation never substitutes for either authorization or
capacity.

## Evidence boundary

The implementation has deterministic unit and composed local runtime tests, a 16-case seed suite and a
credential-free example. It inherits the Day91 separate-process stdio SDK boundary, but Day92 has not run a
real Authorization Server, production JWKS, remote HTTP deployment, durable authorization store, distributed
rate limiter, load test, failure drill, monitoring or alert delivery. Production readiness remains
`MORE_EVIDENCE_NEEDED`.
