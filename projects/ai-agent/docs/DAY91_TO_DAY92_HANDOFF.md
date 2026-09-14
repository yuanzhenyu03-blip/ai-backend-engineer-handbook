# Day91 to Day92 Handoff

Day92 may add authentication and tenant isolation infrastructure around the Day91 Server. It must preserve
the Day89–Day91 application and protocol contracts.

## Stable inputs for Day92

- MCP specification/schema `2026-07-28` and SDK integration pin `mcp==2.2.0`;
- SDK-private Server Adapter and application-owned request DTOs;
- pre-handler backpressure for Tool, Resource and Prompt paths;
- application-issued Tool and Resource permits;
- operation identity, idempotency conflict and pending reconciliation rules;
- Tool-level error versus Protocol error distinction;
- Resource pre-read scope and post-read content validation;
- Prompt pre-render and post-render validation with no system-policy authority;
- signed revision-bound Tool inventory cursors;
- Client-side correlation, output validation and Committer authority from Day90.

## Day92 owns

- authenticated principal extraction at the transport edge;
- authorization-server and audience/issuer validation;
- tenant membership and resource-scope evidence from trusted infrastructure;
- denial behavior that avoids tenant/resource enumeration;
- credential rotation and negative auth integration tests.

## Day92 must not absorb

- model/framework authority;
- application operation identity from peer payloads;
- automatic retry of unknown outcomes;
- durable business Committer inside MCP handlers;
- production remote deployment and observability, which remain Day93 work;
- model + MCP capstone orchestration, which remains Day94 work.

## Continuing flow

```text
authenticated transport identity
→ application authorization facts
→ Day91 Server Adapter request conversion
→ capacity + handler admission
→ controlled service candidate
→ Day90 Client correlation and output validation
→ Committer
```

## Evidence boundary

Current evidence is separate-local-process stdio `INTEGRATION_RUNTIME`. Production auth, durable stores,
remote deployment, monitoring, load/backpressure testing and production failure drills remain NOT RUN.
