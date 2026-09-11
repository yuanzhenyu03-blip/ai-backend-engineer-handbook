# Day90 to Day91 Handoff

Day91 may replace the controlled stdio fixture with a deliberately designed MCP Server. It must keep Day90's
Client and Day89's application contracts stable.

## Stable inputs for Day91

- MCP specification/schema: `2026-07-28`;
- SDK integration pin: `mcp==2.2.0`;
- application DTOs: `MCPRequestDTO`, `MCPResponseDTO`;
- trusted local identity: `MCPRequestBinding`;
- immutable retry lineage and Tool idempotency identity;
- correlation and `ProtocolObservation` classifications;
- pre-read Resource metadata validation and post-read content validation;
- external Prompt treatment as untrusted data;
- output validation and Committer authority;
- production readiness: `MORE_EVIDENCE_NEEDED`.

## What Day91 owns

Day91 should teach the Server side of Resources, Tools and Prompts: declarations, handlers, method semantics,
input/output contracts and Server lifecycle. It may evolve `tests/fixtures/day90_mcp_stdio_server.py` into a
bounded Server artifact, but should not treat the Day90 fixture as production design.

## What Day91 must not absorb

- application authorization or tenant-policy authority;
- application operation identity;
- Client request binding or retry decisions;
- model system/developer instructions;
- durable business Committer;
- Day92 authentication/authorization infrastructure;
- Day93 production remote lifecycle and observability;
- Day94 model + MCP capstone orchestration.

## Required continuing flow

```text
application-approved request
→ durable binding and dispatch evidence
→ Day90 Client Adapter
→ Day91 Server handler
→ SDK-private response conversion
→ MCPResponseDTO
→ local correlation
→ ProtocolObservation
→ output validation
→ Committer
```

## Day91 starting tests

1. a Tool-level failure remains a valid protocol result;
2. Resource listing/reading never grants application tenant authority;
3. Prompt messages cannot become application system policy;
4. malformed Server output stops inside the Client Adapter;
5. duplicate/conflicting response and unknown-outcome behavior remain unchanged;
6. Day88–Day90 regressions stay green.

Real auth, production Tools, remote deployment, monitoring and failure drills remain future evidence.
