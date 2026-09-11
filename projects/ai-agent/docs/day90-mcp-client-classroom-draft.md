# Day90 Classroom Record — MCP Client Engineering

Recorded 2026-09-11 from the isolated Day90 workspace. No commit, push or PR was created during class.

## Baseline and official evidence

- remote main: `ae63f771d52ca10b03bfde38b1a54a686a27f048`;
- remote Day89 branch and classroom baseline: `61a51167648fb65c2030ca9e3a14d2163eae38d1`;
- main did not contain Day89, so the dirty original checkout was not used;
- current specification/schema observed: `2026-07-28`;
- official Python SDK selected and pinned: `mcp==2.2.0`;
- Python executed: 3.11.5; Python 3.12 was unavailable.

## Actual learner reasoning

The learner classified a post-dispatch connection loss as unknown outcome, rejected immediate retry and denied
durable success. They then added the critical ordering refinement: persist a dispatch marker before the actual
send. For safe retry, they preserved `application_operation_id` and Tool `idempotency_key`, generated a new
`protocol_request_id`, and retained immutable lineage.

The learner rejected SDK response leakage because it breaks the Client Adapter boundary. They chose to preserve
the Day89 contract when the high-level SDK could not accept a caller-supplied request ID, accepting a private
Adapter maintenance cost instead of weakening binding.

The learner consistently required local correlation, application output validation and Committer control. They
rejected unknown response IDs, cross-tenant Resource reads, external Prompt policy mutation, duplicate commits,
conflict selection and post-send cancellation as proof of non-execution.

For lifecycle, the learner ordered shutdown as stop new requests, handle in-flight requests, then close Client.
They placed unresolved dispatched attempts into pending reconciliation. They also correctly distinguished model
Provider integration from MCP Client integration.

## Mental-model corrections

1. A cross-tenant result with a matching request ID does create a `PROTOCOL_RESULT` observation before
   application output validation rejects it; it is not an unknown response.
2. `CallToolResult.isError=true` is a Tool-level failure inside a protocol result, not a JSON-RPC protocol error.
3. `BindingStatus.COMPLETED` means the protocol attempt ended; it does not mean the application operation
   succeeded. `INDIRECT_PROMPT_INJECTION` belongs to `OutputValidationOutcome`, not `BindingStatus`.
4. Capability means support for a method family; it does not prove that one named Tool exists. Inventory and
   input schema are separate evidence.
5. A Resource rejected after it was actually read records `resource_reads=1`; rejection cannot erase an effect.
6. Local real-SDK stdio integration is `INTEGRATION_RUNTIME`, not production. The learner initially promoted it,
   then corrected the final labels to `INTEGRATION_RUNTIME` / `MORE_EVIDENCE_NEEDED`.
7. The class briefly drifted into JWT detail and introduced terminology too quickly. Teaching returned to the
   Day90 Client boundary, added plain-language definitions and separated future Day92 auth work.
8. The earlier hypothetical MCP Prompt `role=system` was corrected: current schema roles are `user` and
   `assistant`; `system` would fail SDK/schema validation.

## Mental-model evolution

```text
real SDK appears able to own the call
→ high-level API cannot preserve pre-bound request identity
→ SDK-private seam keeps exact request ID and SDK types isolated
→ correlation proves protocol ownership only
→ output validation decides content acceptance
→ Committer alone controls business transition
```

```text
Tool / Resource / Prompt all use MCP
→ their wire pipeline is shared
→ their application entry and model roles differ
→ Research Agent mediates every path
```

## Executed implementation

- dependency-free current wire codec and byte transport;
- exact-ID SDK-private Adapter pinned to 2.2.0;
- separate stdio Server fixture with controlled Tool, Resource and Prompt;
- Tool inventory and input-schema preflight;
- inventory-generation invalidation;
- pre-dispatch abort and post-dispatch unknown transitions;
- pre-read Resource admission and post-read content accounting;
- SDK validation failure isolation;
- deterministic example and Day90 seed grader.

The first seed run passed 12 of 13 cases. The malformed-response case was incorrectly caught by a broader
`ValueError` branch before `MCPCodecError`, so the grader reported the wrong classification. Reordering the
exception handlers fixed the classification; the seed was then rerun as part of final validation. This was a
grader-control-flow bug, not evidence that the malformed response was safe.

During final review, a proven-not-sent transport failure was tightened from the generic `PROTOCOL_ERROR` label
to `PRE_DISPATCH_ABORTED`, matching the classroom distinction between pre-dispatch certainty and a peer
protocol error. The corresponding seed expectation was updated before the final 13/13 run.

## Evidence boundary

The SDK Client and Server ran as separate local processes over stdio. No model Provider API, real credential,
OAuth flow, remote HTTP Server, production Tool, business database, deployment, monitoring platform, load test
or production failure drill ran. Production readiness remains `MORE_EVIDENCE_NEEDED`.

```text
final_synthesis_author: LEARNER
independent_synthesis: ASSESSED_WITH_CORRECTIONS
```
