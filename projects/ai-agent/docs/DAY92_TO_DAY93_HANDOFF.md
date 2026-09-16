# Day92 to Day93 Handoff

Day93 may add remote transport lifecycle, retry, versioning and observability around the Day92 security
boundary. It must preserve the Day89–Day92 protocol, operation identity and least-authority contracts.

## Stable inputs for Day93

- MCP specification/schema `2026-07-28` and SDK pin `mcp==2.2.0` observed during Day92;
- HTTP per-request authentication and stdio trusted-Launcher identity separation;
- minimized application-owned principal with no raw bearer credential;
- issuer, audience, signature, expiration, not-before and subject validation outcomes;
- current revocation, scope, tenant membership and exact capability authorization;
- principal-bound Tool permits and render/read-only Prompt/Resource permits;
- operation identity duplicate/conflict handling;
- enumeration-resistant Resource denial;
- pre-auth cheap edge protection and post-auth application capacity admission;
- Day91 handler, candidate-result, pending-reconciliation and no-Committer rules;
- Day90 Client correlation, output validation and Committer authority.

## Day93 owns

- remote HTTP connection lifecycle, timeout budgets and cancellation propagation;
- retry policy driven by proof of pre-dispatch failure versus unknown outcome;
- JWKS refresh/cache observability without inventing trust on refresh failure;
- remote protocol/version compatibility and deployment configuration;
- security and lifecycle metrics with credential-safe logging;
- reconciliation scheduling and operational alerts;
- load, backpressure and controlled failure drills.

## Day93 must not absorb

- identity or membership from Client payloads;
- token/request-provided signing keys;
- retry with a new operation identity to bypass duplicate/conflict checks;
- automatic retry of `PENDING_RECONCILIATION` operations;
- Resource URI or Prompt text as authorization evidence;
- durable Committer authority inside MCP Server handlers;
- full Agent + MCP capstone orchestration, which remains Day94 work.

## Continuing flow

```text
remote Client
→ edge transport protection
→ authentication
→ current application authorization
→ exact permit
→ remote lifecycle and capacity controls
→ Day91 handler + controlled service
→ candidate/unknown outcome
→ Day90 correlation and output validation
→ reconciliation or Committer
```

## Evidence boundary

Day92 supplies deterministic local security validation and inherits Day91's separate-process stdio SDK
integration. Real Authorization Server/JWKS integration, remote HTTP deployment, durable authorization and
operation stores, distributed rate limiting, monitoring, load tests and production failure drills are NOT
RUN. Continue to report `production_readiness = MORE_EVIDENCE_NEEDED` until those gaps have executed evidence.
