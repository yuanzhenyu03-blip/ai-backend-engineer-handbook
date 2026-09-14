# Day91 — MCP Server Engineering Design

> Baseline: `2dd3c86265c6935ec0f70cd118418dcb2406c29b`
> MCP specification/schema: `2026-07-28`
> SDK integration pin: `mcp==2.2.0`
> Evidence: `INTEGRATION_RUNTIME`
> Production readiness: `MORE_EVIDENCE_NEEDED`

## Decision

The MCP SDK is confined to `mcp_server_adapter.py`. The Adapter converts SDK `Context` and validated method
arguments into application-owned `ServerToolRequest`, `ServerResourceRequest` and `ServerPromptRequest`
values. Coordinators apply capacity admission before handlers. Handlers receive only narrow application ports
created through startup dependency injection.

The Server returns candidates and errors. It never owns Client-side correlation, final output validation or
the durable business Committer.

## Responsibility map

| Component | Owns | Must not own |
| --- | --- | --- |
| Server Adapter | SDK types, registration, request conversion, wire error mapping | tenant truth, durable commit |
| Coordinator | pre-handler capacity gate and lease release | business authorization |
| Tool handler | app admission, idempotency claim, controlled service, server-side semantic output check | Committer |
| Resource handler | scope admission before read, content safety validation after read | authorization derived from URI |
| Prompt handler | argument validation, code-owned rendering, rendered-message validation | system policy, automatic Tool/Resource calls |
| Lifecycle | close admission, drain in-flight work, preserve unknown identity | guessing success/failure |
| Inventory paginator | complete pages and signed revision-bound cursors | application execution permission |

## Total flow

```text
Model / Framework
→ ToolProposal
→ Application checks
→ MCPRequestBinding + dispatch marker
→ Day90 MCP Client
→ Day91 Server Adapter
→ application-owned Server request
→ pre-handler backpressure
→ application handler + narrow service
→ candidate result or bounded error
→ MCP Client DTO conversion
→ local correlation
→ ProtocolObservation
→ application output validation
→ Committer
→ optional durable transition
```

## Tool boundary

```text
SDK Context + query
→ ServerToolRequest
→ capacity gate
→ application admission / application-issued permit
→ idempotency claim
→ controlled service
→ semantic output validation
→ candidate
```

- capacity rejection occurs before the handler and maps to Protocol error;
- application, duplicate, identity-conflict and output rejection map to Tool-level `isError=true`;
- `outputSchema` validates shape but cannot replace tenant/provenance/policy validation;
- two protocol request IDs may still represent one application operation;
- no handler dependency exposes a Committer or durable store.

## Resource boundary

```text
SDK URI template match
→ ServerResourceRequest
→ capacity gate
→ application scope admission
→ controlled read
→ untrusted-content validation
→ candidate content or Protocol error
```

Cross-tenant rejection occurs before read (`resource_reads=0`). Indirect prompt injection is discoverable only
after read (`resource_reads=1`) but produces no model-context candidate. Resource errors have no Tool-style
`isError` half-result. The dynamic Resource is listed under `resources/templates/list`; the static
`resources/list` is honestly empty because SDK 2.2.0 does not inject `Context` into static Resource handlers.

## Prompt boundary

```text
SDK prompt name/arguments
→ ServerPromptRequest
→ capacity gate
→ pre-render argument safety
→ code-owned template render
→ post-render message safety
→ user-role candidate only
```

Rejected arguments render zero times. A dangerous rendered message renders once, but performs zero Tool calls
and zero Resource reads. Prompt text is not executable authority and cannot become system/developer policy.

## Inventory and pagination

The Server exposes two controlled Tools and one Tool per page. Cursors are HMAC-signed, bind an offset to the
hash of the complete inventory, and reject malformed, forged, out-of-range or stale values with `-32602`.
After `tools/list_changed`, a Client discards every old page and restarts without a cursor. It never merges
pages across revisions.

## Lifecycle and backpressure

```text
ACCEPTING
→ shutdown closes new admission
→ DRAINING existing operation IDs
   ├─ all complete → STOPPED / CLEAN
   └─ timeout → cancel handler tasks
                + preserve IDs
                + PENDING_RECONCILIATION
                + STOPPED
```

Cancellation is a runtime fact, not proof of business failure. A late completion cannot overwrite pending
reconciliation. Backpressure rejects before Tool, Resource or Prompt handlers and is a Protocol error.

## SDK isolation

Imports from `mcp`, `mcp_types` and SDK exception/context packages are permitted only in
`mcp_server_adapter.py`, the controlled stdio fixture and SDK integration tests. Application modules compile
and test without the SDK installed.

## Evidence and limits

The real integration runs a pinned SDK Client and Server as separate local processes over stdio. This supports
`INTEGRATION_RUNTIME`, not `PRODUCTION`. Real authentication, authorization infrastructure, durable
idempotency storage, database-backed reconciliation, remote HTTP deployment, monitoring, load testing,
failure drills and production Tools remain NOT RUN.
