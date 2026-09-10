# Day89 Classroom Record — MCP Foundations and Protocol Model

Recorded 2026-09-10. This is the guided classroom record from the isolated
Day89 workspace. It is not a published lesson or production approval.

## Baseline and scope

- pinned remote `main`: `ae63f771d52ca10b03bfde38b1a54a686a27f048`;
- Decision 010 amends Decision 009: PydanticAI remains the default course
  Adapter and the LangGraph-shaped translator remains dependency-free;
- Day89 was planned/not started at the baseline;
- real MCP Client, Server, SDK, remote transport, authentication, production
  Tool, database and deployment were not run;
- evidence level: `EXECUTED_LOCAL_RUNTIME`;
- production readiness: `MORE_EVIDENCE_NEEDED`.

## Actual learner reasoning preserved

The learner correctly established that a revoked current grant stops at the
Committer, with zero MCP sends, zero external Tool calls and no durable
transition. The learner also identified that protocol success must become an
observation and pass output validation before application state can change.

For identity, the learner stated that protocol request IDs may change while the
application operation ID remains stable and retries rely on idempotency. The
learner required the application operation ID to remain in local
`MCPRequestBinding` and rejected peer attempts to override that binding.

For untrusted content, the learner required tenant, permission and resource
checks before Resource content is read. The learner rejected an external Prompt
attempt to change Committer policy. The learner also concluded that each
current request has independent version and capability evidence.

For failure and rollback, the learner required unknown responses to have no
business effect, classified identical and conflicting repeated responses as
duplicate and conflict, and sent uncertain dispatched operations to
`PENDING_RECONCILIATION`. The learner preserved local binding during a bad
policy incident and limited containment to the affected policy set. The learner
distinguished recovery of new traffic from incident closure.

For reconciliation, the learner required authoritative evidence, rejected
cross-tenant evidence, used existing successful-report evidence instead of
replaying the Tool, and separated truthful side-effect status from an
authorization-violation record.

In the English interview, the learner gave concise correct foundations:

- “MCP capability does not imply that application authorization has been
  granted.”
- an application observation still requires application validation and a
  Committer decision;
- timeout after possible send must not be blindly retried because the side
  effect may already exist.

## Misconceptions and precise corrections

1. The learner initially required a protocol request ID to equal an application
   operation ID. The correction established separate identity domains connected
   by a trusted local binding. One operation may have multiple request attempts.
2. The learner called an injected MCP Prompt a direct injection. Because the
   instruction came from an external Server, the course classified it as
   indirect prompt injection.
3. The learner used authentication when explaining cross-tenant denial. The
   correction separated identity proof from authorization over the current
   tenant and resource.
4. The learner initially said a current `2026-07-28` request should be rejected
   without the historical initialization handshake. Official current evidence
   shows a stateless, self-describing request model; legacy lifecycle semantics
   require an explicit old-version boundary.
5. The learner proposed that the protocol DTO, MCP version and policy version
   could all be replaced with the Day90 Client. The correction limited
   replaceability to transport, codec and SDK-private implementation. Application
   DTOs, version admission, policy and Committer authority remain application
   owned.
6. The final synthesis described MCP mainly as a transport formatting protocol.
   The refined model is an application protocol using JSON-RPC messages over a
   transport; Transport itself owns no authorization or business state.

## Mental-model evolution

```text
Framework or MCP appears to execute work
        ↓
Framework only proposes; MCP only exchanges protocol messages
        ↓
local binding converts protocol identity into application context
        ↓
ProtocolObservation remains evidence
        ↓
Output validation + current Committer decision
        ↓
optional durable transition
```

The learner's independent final synthesis correctly connected Framework
Adapter, MCP, application core, capability versus authorization, the two ID
domains, correlation, observation, output validation, Committer and
reconciliation. It required only the precision corrections listed above.

```text
final_synthesis_author: LEARNER
independent_synthesis: ASSESSED_WITH_CORRECTIONS
```

## Executed classroom evidence

- Day89 focused and grader tests: 21 passed;
- Day88 Adapter regression: 43 passed;
- cumulative tests: 560 passed;
- Day83–Day86 seed regression: 26, 16, 18 and 25 passed;
- Day89 seed: 16 passed;
- deterministic example, syntax, JSON/JSONL and diff validation: passed.

The classroom implementation used synthetic data and Fake Transport only. It
does not establish a real MCP integration.
