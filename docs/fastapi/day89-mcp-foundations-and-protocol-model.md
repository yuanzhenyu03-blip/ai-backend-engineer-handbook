# Day 89 — MCP Foundations and Protocol Model

## 1. Lesson Metadata

- Status: ✅ Completed (guided classroom scope)
- Template: `LESSON_TEMPLATE_v2`
- Version: 1.0
- Difficulty: Intermediate
- Estimated study time: 4–5 hours
- Prerequisite: Day88 — Agent Runtime Framework Selection Behind a Replaceable Adapter
- Next lesson: Day90 — MCP Client Engineering
- Engineering artifact: SDK-independent MCP DTOs, Fake Transport, correlation model, seed eval and Day90 handoff
- Evidence: `EXECUTED_LOCAL_RUNTIME`; production readiness `MORE_EVIDENCE_NEEDED`

## 2. Learning Objectives

After this lesson, you should be able to:

1. explain the distinct responsibilities of an MCP Host, Client, Server and application core;
2. distinguish capability discovery from application authorization;
3. keep protocol request identity separate from application operation identity;
4. validate and correlate protocol messages without granting business authority;
5. treat Resources and Prompts as untrusted external input;
6. classify duplicate, conflict and unknown outcomes without duplicating side effects;
7. preserve stable application contracts when Day90 introduces a real MCP Client;
8. defend these boundaries in an English system-design interview.

## 3. Why This Matters

MCP lets an application exchange tools and context with external systems through a standard protocol. That
interoperability also creates a dangerous shortcut: teams may mistake “the Server exposes this Tool” for “the
current user is allowed to execute it,” or mistake a successful protocol response for committed business truth.

In a multi-tenant Research Agent, those mistakes can publish duplicate reports, read another tenant's document,
let an external Prompt alter policy, or lose track of an operation after a timeout. Day89 prevents that coupling
before Day90 adds a real Client and network boundary.

## 4. Roadmap Position

```text
Day72–Day86 application-owned Provider, Tool, state and security contracts
        ↓
Day88 replaceable Framework Adapter: framework output is only ToolProposal
        ↓
Day89 SDK-independent MCP protocol model: messages are only requests/evidence
        ↓
Day90 real MCP Client behind the stable contracts
        ↓
Day91–Day94 Server, auth/tenant isolation, lifecycle hardening and capstone
```

Day89 adds a protocol layer; it does not build a second security backend or pre-implement Day90–Day94.

## 5. Lesson Map

```text
Responsibilities
→ current wire model
→ capability versus authorization
→ request ID versus operation ID
→ Fake Transport and correlation
→ ProtocolObservation and output validation
→ untrusted Resource/Prompt
→ timeout, reconciliation and rollback
→ Day90 replacement boundary
```

## 6. Core Mental Model

```text
Framework output
→ private Adapter
→ ToolProposal
→ Committer current-fact gate
→ MCPRequestDTO
→ protocol validation
→ local MCPRequestBinding
→ Transport / Server
→ MCPResponseDTO
→ correlation
→ ProtocolObservation
→ output validation
→ Committer
→ optional durable transition
```

MCP standardizes exchange. It never receives application approval, operation ownership or durable-state
authority merely because a message is valid.

## 7. Main Concepts

### Concept 1: Host, Client, Server and application core

#### Tech Lead Question

Where does MCP end, and where does application responsibility begin?

#### Student Thinking

The learner described MCP as a formatted JSON-RPC transport and correctly placed tenant, identity, resource,
authorization and state validation in the application core.

#### Student Answer

“Application core承担应用的状态、资源、身份、租户、授权等验证边界。”

#### Tech Lead Review

The ownership conclusion is correct. The precision correction is that MCP is an application protocol carried
over a Transport, not the Transport itself. The future Client translates and correlates wire messages; the
Server provides Resources, Prompts and Tools; the application owns business policy and state.

#### Engineering Thinking

Keeping these responsibilities separate lets a team replace an SDK or Transport without moving authorization
into network code. Transport failure and operation failure also remain distinct.

#### Production Example

A Research Services Server can advertise `publish_research_report`; the application still checks the current
tenant, grant, approval, policy, fence and operation state before dispatch.

#### Framework Connection

PydanticAI remains inside the Day88 Adapter. Future MCP SDK objects remain inside the Day90 Client Adapter.

#### Exercise

Draw the component that can see the production Tool client. It must be the application-owned Committer, not the
Framework Adapter or MCP Server.

### Concept 2: Current request model and capability

#### Tech Lead Question

Does capability discovery authorize a Tool, and can a request inherit the previous request's capabilities?

#### Student Thinking

The learner consistently rejected capability as authorization and concluded that current requests are
independent.

#### Student Answer

“MCP capability does not imply that application authorization has been granted.”

#### Tech Lead Review

Correct. The official `2026-07-28` schema uses JSON-RPC 2.0 and self-describing requests with protocol version
and client capabilities carried per request. Servers must not infer capabilities from earlier requests. The
historical initialization/session lifecycle is not a current-version prerequisite.

#### Engineering Thinking

Version and capability evidence are protocol compatibility inputs. Application authorization is a current
business decision. A local version-admission policy decides which advertised versions can execute.

#### Production Example

Request 1 observes `tools`. Request 2 has no such evidence. Request 2 fails before binding or send, even when
the same Server handled request 1.

#### Framework Connection

This repeats Day88's rule: framework or protocol capability is not execution authority.

#### Exercise

Given a valid message with a revoked current grant, identify the first gate. Answer: Committer; protocol
validation does not run and no binding exists.

### Concept 3: Protocol identity and business identity

#### Tech Lead Question

Must the protocol request ID equal the application operation ID?

#### Student Thinking

The learner first rejected two unequal IDs, then corrected the model after tracing the local binding and retry
path.

#### Student Answer

Final answer: preserve the operation ID, create a new request ID for a safe retry, and retain the old binding for
audit.

#### Tech Lead Review

`protocol_request_id` correlates one request/response attempt. `application_operation_id` represents one
business intent and remains stable across attempts. `MCPRequestBinding` is the trusted local mapping; a peer
payload cannot replace it.

#### Engineering Thinking

One operation may have many protocol attempts. The application-generated idempotency key remains stable. Old
bindings are immutable retry and incident evidence.

#### Production Example

`mcp-request-7 → op-report-42` and `mcp-request-8 → op-report-42` are valid retry lineage after authoritative
evidence proves retry safe. A response claiming `op-report-99` conflicts with the local binding.

#### Framework Connection

Framework run IDs and SDK call IDs are also untrusted correlation inputs; neither becomes operation identity.

#### Exercise

Classify an unknown response ID. Answer: `UNKNOWN_RESPONSE`, no application operation context and no business
effect.

### Concept 4: Observation, validation and durable state

#### Tech Lead Question

Why can a successful protocol result not update business state directly?

#### Student Thinking

The learner required result → observation → output validation and a Committer decision.

#### Student Answer

“The application observation is merely a candidate; it still requires … verification by a committer.”

#### Tech Lead Review

An observation is protocol evidence, not a trusted business fact. Correlation recovers application context;
output validation checks result schema and tenant/resource semantics; Committer re-reads current application
facts and owns the durable transition.

#### Engineering Thinking

Protocol validity, semantic validity, authorization and state transition are different failure domains. Keeping
them separate prevents a schema-valid peer response from becoming application truth.

#### Production Example

A response may be valid JSON-RPC yet reference a report owned by another tenant. Correlation succeeds, output
validation rejects, and no durable transition occurs.

#### Framework Connection

The future SDK Adapter must convert `CallToolResult` into the application-owned DTO before correlation. SDK
types cannot enter Committer or durable storage.

#### Exercise

List the successful path and three fail-closed points: current authorization, protocol/schema validation and
output/tenant validation.

### Concept 5: Resource, Prompt and unknown outcomes

#### Tech Lead Question

Can the application fetch a Resource first and filter it later? Can a Server Prompt change application policy?

#### Student Thinking

The learner rejected both and correctly sent a post-dispatch timeout to reconciliation.

#### Student Answer

Tenant/resource authorization must occur before the read; external Prompt instructions cannot modify Committer
policy; possible-send timeout is not immediately retried.

#### Tech Lead Review

A URI is an identifier, not ownership evidence. Validate metadata before dereference. A Server Prompt is
untrusted external content; injected instructions from it are indirect prompt injection. Timeout after possible
send retains the original binding and becomes `OUTCOME_UNKNOWN` / `PENDING_RECONCILIATION`.

#### Engineering Thinking

Reconciliation uses authoritative downstream evidence and never invents a new operation. Fact status and
compliance status remain separate: a real effect is recorded truthfully even when it also caused an
authorization violation.

#### Production Example

If an existing report is found by the stable idempotency key, the application validates operation, tenant,
resource and report identity, then proposes a fact repair. It does not publish again.

#### Framework Connection

Prompt text may be shown to a model only as provenance-bound untrusted data. Neither Framework nor MCP content
can mutate the system policy.

#### Exercise

For cross-tenant reconciliation evidence, assert three absent effects: no MCP send, zero external Tool calls and
no durable transition.

## 8. Common Misconceptions

### “Request ID must equal operation ID”

❌ Equality proves correlation.
✅ A trusted local binding connects two deliberately different identity domains.

### “Authentication prevents cross-tenant access”

❌ Knowing who the caller is proves permission.
✅ Authentication establishes identity; authorization decides access to the current tenant/resource.

### “Schema-valid Prompt is safe instruction”

❌ Correct structure grants policy authority.
✅ External Prompt content remains untrusted and cannot change the Committer.

### “Current MCP still requires initialize/session”

❌ Apply an older lifecycle to every revision.
✅ Select semantics by an explicitly admitted specification version; current `2026-07-28` is self-describing.

### “A new request ID makes retry safe”

❌ A new protocol identity proves the old effect did not happen.
✅ Reconciliation and Tool idempotency evidence must establish retry safety first.

## 9. Engineering Trade-offs

An SDK-independent DTO adds conversion code but protects the application from SDK churn. Strict version and
method allowlists reduce accidental compatibility but require explicit migrations. Immutable binding history
costs storage but preserves late-response handling and auditability. Fail-closed unknown outcomes may delay
work, but blind retries can duplicate irreversible side effects.

Fake Transport provides fast deterministic failure injection. It cannot prove real Server, network, SDK,
authentication, Tool-idempotency or production behavior.

## 10. Hands-on Exercises

### Exercise 1: Correlation table

Question: classify unknown, duplicate and conflicting response IDs.
Think First: protocol identity does not decide durable state.
Starter Artifact: `tests/test_day89_mcp_protocol_model.py`.
Expected Output: `UNKNOWN_RESPONSE`, `DUPLICATE`, `CONFLICT`, all with no durable transition.
Explanation: the local binding and response fingerprint are authoritative.
Follow-up Question: what should happen to a late response after the operation is terminal?

### Exercise 2: Timeout boundary

Question: compare timeout before send with timeout after possible send.
Think First: can the system prove zero external effect?
Starter Artifact: `mcp_fake_transport.py`.
Expected Output: before-send removes binding; possible-send retains binding and reconciles.
Explanation: uncertainty is preserved rather than rewritten as failure.
Follow-up Question: when may a new request ID be created under the original operation?

### Exercise 3: Bad policy rollback

Question: contain a policy that conflates capability, authorization and operation identity.
Think First: separate undispatched work from possibly dispatched work.
Starter Artifact: the 16-case Day89 seed eval.
Expected Output: pause affected new requests; preserve history; reconcile uncertain operations; rerun focused,
cumulative and seed regressions before recovery.
Explanation: recovery of traffic and incident closure are separate gates.
Follow-up Question: what unresolved evidence prevents closure?

## 11. Relevant Framework Connections

PydanticAI remains the default Day88 course Adapter. Decision 010's dependency-free LangGraph-shaped translator
continues to prove contract replaceability, not LangGraph runtime integration. Both Framework paths end at the
same application `ToolProposal`. Day90 may add an MCP SDK Adapter, but the SDK remains private and produces the
same Day89 DTOs and observations.

## 12. AI Backend Connections

The continuing multi-tenant Research Agent uses `search_documents`, `fetch_document` and
`publish_research_report`. MCP makes those services discoverable and callable across systems. Application
controls still bind each call to the principal, tenant, resource, approval, operation, idempotency key and
current policy. Retrieved Resources and Prompts remain injection-capable external data.

## 13. English Interview

### Key Vocabulary

capability; authorization; correlation; operation identity; observation; output validation; reconciliation.

### Useful Expressions

- “Capability discovery describes protocol support; it does not grant application authorization.”
- “A protocol result is evidence, not a durable business fact.”
- “I preserve the operation ID and reconcile an unknown outcome before retrying.”

### Beginner Question

Is MCP capability the same as authorization?
Strong answer: No. Capability says what the Server can support; the application checks whether the current
caller and operation may use it.

### Intermediate Question

Why is a request ID different from an operation ID?
Strong answer: A request ID correlates one protocol attempt. The operation ID identifies stable business intent
across retries and reconciliation. A local binding connects them.

### Senior Question

How do you handle timeout after possible send?
Strong answer: Preserve the original binding and idempotency identity, mark the outcome unknown, avoid blind
retry, and use authoritative reconciliation evidence before repair or retry.

### Common Weak Answer

“The SDK returned success, so I update the database.”

### Strong Answer

“I translate SDK output into an application DTO, correlate through the local binding, validate output scope and
current policy, then let the Committer decide the durable transition.”

## 14. Mental Model Summary

```text
MCP capability       ≠ application authorization
protocol request ID  ≠ application operation ID
protocol result      ≠ durable business success
Resource URI         ≠ ownership or read permission
Server Prompt        ≠ application policy
timeout after send   = unknown + reconciliation
Fake Transport       = EXECUTED_LOCAL_RUNTIME, not integration
```

## 15. Today's Takeaway

MCP makes integration standard; the application keeps control. Validate current authorization before send,
bind protocol attempts to stable application operations locally, treat responses as observations, validate
external content before use, and preserve uncertainty when external effects may already exist.

## 16. Before Next Lesson Checklist

- [ ] I can separate Host, Client, Server, Transport and application responsibilities.
- [ ] I can explain the current self-describing request model and historical session model.
- [ ] I can defend capability versus authorization.
- [ ] I can map many protocol attempts to one application operation.
- [ ] I can classify unknown, duplicate, conflict and possible-send timeout.
- [ ] I can explain why Resource/Prompt content stays untrusted.
- [ ] I can run the 21 Day89 tests, 16-case seed eval and deterministic example.
- [ ] I can state what Day90 may replace and what contracts it must preserve.
- [ ] I can answer the core questions in English.
