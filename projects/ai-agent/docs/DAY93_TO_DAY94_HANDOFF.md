# Day93 to Day94 Handoff

Day94 may compose the Agent runtime with the MCP Client/Server boundaries. It must preserve the
application-owned identities, authority separation and remote lifecycle evidence established through
Day93.

## Stable inputs for Day94

- application-owned protocol DTOs and operation/resource bindings from Day89;
- Client correlation, output validation and Committer boundary from Day90;
- candidate-only Tool/Resource/Prompt handlers and shutdown lifecycle from Day91;
- minimized principal, current authorization, exact permits and tenant isolation from Day92;
- application-owned `FailureEvidence` with separate dispatch and execution certainty;
- one absolute deadline and bounded phase budgets;
- retry policy separated from transport, reconciliation and Committer;
- operation/idempotency identity preserved across attempts;
- fresh protocol request identity and incremented attempt number per retry;
- conditional pre-dispatch state transition so only one worker dispatches;
- read-only authoritative reconciliation and bounded operational alerts;
- generation-scoped remote correlation and late-response validation;
- generation-scoped protocol/version/capability preflight;
- fail-closed unknown-key JWKS refresh behavior;
- credential-safe logs, bounded metrics and non-authoritative traces;
- global pre-auth shedding versus post-auth tenant capacity admission.

## Day94 owns

- an executable Agent loop that selects an MCP capability through current policy;
- end-to-end propagation of operation, idempotency, deadline and cancellation context;
- composition of Day92 authorization permits with Day93 lifecycle gates;
- the complete candidate-result → observation → validation → Committer path;
- human-control checkpoints for consequential Tool actions;
- end-to-end recovery after timeout, reconnect and process restart;
- a capstone scenario and operator-facing evidence report.

## Day94 must not absorb

- transport or SDK exceptions into application core;
- identity, tenant, authorization or capacity priority from model/payload text;
- automatic retry of possibly executed or pending-reconciliation operations;
- a new operation identity as a duplicate/conflict bypass;
- Tool execution access inside reconciliation;
- durable Committer authority inside an Agent, handler, adapter or retry policy;
- logs, traces or metrics as business evidence;
- production-readiness claims based only on controlled loopback execution.

## Required composition

```text
Agent intent + human policy
→ application operation identity and parent deadline
→ MCP discovery/version preflight
→ Day92 authentication + current authorization + exact permit
→ Day93 capacity and dispatch gates
→ Day91 handler + controlled service
→ candidate result / unknown outcome
→ Day90 correlation + protocol observation + output validation
→ reconciliation or the sole Committer
→ durable application transition
```

## Evidence boundary

Day93 supplies deterministic local validation and controlled remote runtime evidence using an independent
loopback Streamable HTTP process and the real Python MCP SDK. It does not supply production Authorization
Server/JWKS integration, durable distributed operation stores, distributed rate limiting, production
telemetry, load tests or production fault drills. Day94 must continue to report
`production_readiness = MORE_EVIDENCE_NEEDED` unless those paths are actually executed and recorded.

## First Day94 integration question

When an Agent resumes after a crash and finds `DISPATCH_STARTED` without a trusted result, which component
may query authority, which component may propose a transition, and which single component may make that
transition durable?
