# Day89 — MCP Foundations and Protocol Model

> Baseline: `ae63f771d52ca10b03bfde38b1a54a686a27f048`
> Evidence level: `EXECUTED_LOCAL_RUNTIME`
> Production readiness: `MORE_EVIDENCE_NEEDED`

## Scope

Day89 places an SDK-independent MCP protocol boundary outside the application
core built during Day79–Day88. It does not implement a complete MCP Client,
Server, OAuth flow, remote transport, production Tool or database.

MCP standardizes exchange with external systems. It does not receive the
application's authorization, approval or durable-state authority.

## Current protocol evidence

The official specification and schema observed on 2026-09-10 identify
`2026-07-28` as the current protocol revision and JSON-RPC `2.0` as the message
envelope. Requests carry their own protocol version and client capabilities.
Servers must not infer capabilities from prior requests.

The current revision is stateless at the protocol core. The historical
`initialize` / `notifications/initialized` handshake and `Mcp-Session-Id` are
not required by the current wire model. A legacy implementation may support an
older revision only through an explicit, versioned compatibility boundary.

Recorded sources are in `research/day89-mcp-spec-evidence.jsonl`.

## Responsibility boundary

| Component | Owns | Does not own |
| --- | --- | --- |
| MCP Host | application composition, user interaction, policy and audit entry | automatic access to every Server capability |
| future MCP Client | wire conversion, method/version checks, transport and correlation | business authorization or durable state |
| MCP Server | Resources, Prompts, Tools and protocol results | application approval, tenant policy or operation identity |
| application core | current authorization, tenant/resource binding, operation identity, idempotency, output validation, reconciliation and Committer | SDK-private wire objects |

## Bounded Day89 flow

```text
Framework output
→ Day88 private Framework Adapter
→ application ToolProposal
→ Committer re-reads current facts
→ SDK-independent MCPRequestDTO
→ version / method / params / per-request capability validation
→ local MCPRequestBinding
→ Fake Transport
→ MCPResponseDTO
→ local response correlation
→ ProtocolObservation
→ application output validation
→ Committer
→ optional durable transition
```

Every fail-closed decision before dispatch creates no binding, sends no MCP
request and causes no durable transition. A result returned by MCP is only
protocol evidence.

## Capability is not authorization

Capability evidence says that a protocol participant can express or handle a
feature. The application separately checks its Tool allowlist, current grant,
tenant, resource, approval, canonical arguments, policy version, fence,
deadline, operation state and reconciliation state.

Capability evidence is request-scoped. A later request cannot inherit the
features observed for an earlier request.

## Identity

`protocol_request_id` correlates one protocol request and response.
`application_operation_id` identifies one business intent and remains stable
across attempts. The application creates and owns the Tool idempotency key.

`MCPRequestBinding` is the trusted local mapping. A peer-provided operation ID
cannot replace it. Retry may create a new protocol request ID while preserving
the operation ID and idempotency key; old bindings remain immutable evidence.

## Result classification

- unknown response IDs have no application operation context;
- identical repeated responses are `DUPLICATE`;
- different responses for one request ID are `CONFLICT`;
- timeout before send removes the provisional binding;
- timeout after possible send preserves the binding and produces
  `OUTCOME_UNKNOWN` / `PENDING_RECONCILIATION`;
- no protocol outcome performs a durable transition directly.

## Resources and Prompts

A Resource URI is an identifier, not proof of ownership or authorization.
Tenant and resource metadata are checked before URI dereference. A cross-tenant
reference causes zero Resource reads.

A Server Prompt is untrusted external content. A schema-valid Prompt cannot
modify application policy, create approval or enter the agent loop as a higher
priority instruction. Suspected injected instructions are classified before
model use.

## Reconciliation and rollback

An unknown operation is reconciled using authoritative downstream evidence,
not a blind Tool replay. Tenant, resource, operation ID and idempotency key must
all match the local binding. Conflicting evidence produces
`RECONCILIATION_CONFLICT` with zero external calls and zero durable transition.

Fact and compliance are separate dimensions. If evidence proves a side effect
occurred, the repair proposal records that fact. A separate
`AUTHORIZATION_VIOLATION` records whether the effect was non-compliant. Only a
Committer may persist a validated repair.

For bad `mcp-protocol-policy-v2`, new requests in the affected set are paused.
Already-dispatched requests retain their original identities and enter
reconciliation where required. Recovery of new traffic does not close the
incident while unknown outcomes or authorization violations remain unresolved.

## Executed evidence

- Python: 3.11.5;
- Day89 focused and seed-grader tests: 21 passed;
- Day88 Adapter regression: 43 passed;
- cumulative tests: 560 passed;
- Day83–Day86 seed regression: 26, 16, 18 and 25 passed;
- Day89 seed: 16 passed;
- deterministic example: passed;
- JSON/JSONL validation and `git diff --check`: passed.

No real MCP Client, MCP Server, remote transport, production authentication,
production Tool, production database or deployment ran. Fake Transport evidence
does not establish `INTEGRATION_RUNTIME`.

## Day90 boundary

Day90 may replace transport, codec and SDK-private implementation details. It
must preserve the application DTOs, local binding authority, observation and
output contracts, application operation identity, current authorization and
Committer control. See `DAY89_TO_DAY90_HANDOFF.md`.
