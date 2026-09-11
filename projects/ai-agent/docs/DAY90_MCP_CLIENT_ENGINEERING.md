# Day90 — MCP Client Engineering Design

> Baseline: `61a51167648fb65c2030ca9e3a14d2163eae38d1`
> MCP specification/schema: `2026-07-28`
> SDK: `mcp==2.2.0`
> Evidence: `INTEGRATION_RUNTIME`
> Production readiness: `MORE_EVIDENCE_NEEDED`

## Decision

Preserve Day89 application DTOs and add two replaceable Client implementations:

1. a dependency-free codec/byte-transport Client for deterministic contract and failure tests;
2. an SDK-private Adapter for real lifecycle and separate-process stdio integration.

The SDK's public high-level Tool API mints request IDs. Because the application must persist binding before
dispatch, Day90 uses the SDK 2.2.0 dispatcher `request_id` option behind a narrow private seam. Any SDK upgrade
must re-run the integration proof; failure may not cause an application-contract downgrade.

## Components

| Component | Owns | Excludes |
| --- | --- | --- |
| `MCPWireCodec` | current JSON-RPC request encoding and response decoding | application identity and policy |
| `MCPByteTransport` | byte exchange and explicit dispatch certainty | correlation and business retry |
| `DependencyFreeMCPClientAdapter` | codec + transport composition | SDK types and durable state |
| `SDKPrivateMCPClientAdapter` | SDK lifecycle, discovery, inventory, exact ID dispatch and DTO conversion | tenant policy, model roles and Committer |
| `MCPProtocolBoundary` | local binding, correlation and protocol observations | direct durable transition |

## Ordering invariant

```text
preflight
→ protocol_request_id
→ durable MCPRequestBinding
→ durable dispatch marker
→ Adapter.exchange
→ MCPResponseDTO or transport observation
```

The Adapter receives an existing binding. It never learns operation identity from the peer.

## Result invariants

- SDK result validation failure: `INVALID_MESSAGE`, no raw payload crosses the Adapter;
- valid JSON-RPC error: `PROTOCOL_ERROR`, binding `COMPLETED`;
- valid Tool `isError=true`: `PROTOCOL_RESULT`, binding `COMPLETED`, no success commit;
- unknown response ID: `UNKNOWN_RESPONSE`, no application context;
- identical repeat: `DUPLICATE`;
- different repeat for one ID: `CONFLICT`;
- possible-send failure/cancellation: `OUTCOME_UNKNOWN` / `PENDING_RECONCILIATION`;
- proven pre-dispatch rejection: `PRE_DISPATCH_ABORTED`.

## Inventory and preflight

Connection discovery supplies protocol version and capabilities. Tool listing supplies names and input schemas.
The Adapter validates a complete paginated snapshot and issues a generation/request-fingerprint preflight
permit. When the lifecycle handler receives `tools/list_changed`, it must call `note_tools_list_changed()` to
invalidate existing permits before refresh. Automatic notification subscription was not run in Day90. This is
protocol readiness, not tenant or business authorization.

## Resource and Prompt boundaries

The application validates Resource tenant and identity metadata before calling the Adapter. A successful read
is counted even when post-read content is rejected. Prompt results remain external data and cannot mutate
application policy or model-system authority.

## Lifecycle ownership

The Adapter owns creation and close of one SDK Client. The application runtime owns the larger shutdown:

```text
stop new application attempts
→ drain response processing through Committer
→ classify unresolved dispatched attempts
→ close Client
```

## Trade-offs and follow-up

The private dispatcher seam is intentional technical debt with a strict version pin. Day91 may replace the
controlled fixture with Server-owned handlers. Day92 owns auth and tenant infrastructure. Day93 owns remote
timeouts, reconnect, observability and production lifecycle. Day94 connects the model runtime.
