# Day89 to Day90 Handoff

Day90 may replace the Fake Transport with a real MCP Client implementation.
It may introduce an SDK-private codec, real network transport and explicit
version support. It must not move SDK types into application contracts.

The following Day89 contracts remain application-owned:

- `MCPRequestDTO` and `MCPResponseDTO`;
- `MCPRequestBinding` and immutable retry lineage;
- `ProtocolObservation` and protocol outcome classification;
- per-request version and capability evidence;
- metadata validation before Resource dereference;
- external Prompt treatment as untrusted content;
- `application_operation_id` and Tool idempotency identity;
- output validation and Committer control of durable transitions.

The real Client must preserve the order:

```text
SDK/wire response
→ SDK-private conversion
→ MCPResponseDTO
→ local correlation
→ ProtocolObservation
→ application output validation
→ Committer
→ optional durable transition
```

Day90 must not claim integration evidence until a real SDK and Server boundary
has executed. Day89 evidence remains `EXECUTED_LOCAL_RUNTIME`.
